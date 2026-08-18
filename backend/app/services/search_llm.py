"""搜索链路 LLM 服务 — 用本地 Ollama 对搜索结果做查询重构/相关性判断/结构化抽取。

对齐 DeepSeek 联网搜索思路:
  - 查询重构: 按单位名生成多组查询(电话地址/法定代表人/官网简介/中标公告)
  - 相关性判断: 给定搜索结果条目(title/url/snippet), 判断是否与目标单位相关
  - 结构化抽取: 从搜索结果/正文中抽取 {电话, 地址, 法定代表人, 邮箱, 官网, 单位简介}
    等字段, 容忍 ```json 围栏与裸 key(复用 llm_enhance._extract_json)。

原则: LLM 是「正则兜底后的精提取层」, 不编造 —— prompt 明确要求"正文不存在则为空"。
"""
import json
import logging
import re

from app.services.llm_enhance import LLMUnavailable, _extract_json, _generate

logger = logging.getLogger("search_llm")

# 结构化抽取的字段与中文标签(对齐 company 字段元数据 + 省份/城市)
# 新增 传真/邮编/办公时间 全量公开联系信息; phones/addresses 支持多值数组(全保留)
_EXTRACT_FIELDS = [
    ("province", "省份"),
    ("city", "城市"),
    ("legal_rep", "法定代表人"),
    ("econ_kind", "企业类型(如 有限责任公司/事业单位)"),
    ("registered_capital", "注册资本(万元, 只填数字)"),
    ("belong_org", "登记机关"),
    ("business_scope", "经营范围"),
    ("contact_person", "联系人"),
    ("contact_phone", "联系电话(座机优先)"),
    ("fax", "传真号码"),
    ("email", "电子邮箱"),
    ("website", "官方网站"),
    ("postal_code", "邮政编码"),
    ("office_hours", "办公时间(如 周一至周五 9:00-17:00)"),
    ("establish_date", "成立日期(YYYY-MM-DD)"),
    ("oper_status", "经营状态(存续/在业/注销等)"),
    ("reg_no", "注册号/统一社会信用代码(18位)"),
    ("credit_code", "统一社会信用代码(18位, 与reg_no相同则填)"),
    ("industry", "所属行业(如 建筑业/医疗/教育/水利等, 企业类单位)"),
    ("contact", "联系电话(座机优先, 兼容旧字段)"),
    ("address", "办公地址"),
    ("summary", "单位简介(一句话)"),
    # 多值(全保留, 供选择主要): 数组
    ("phones", "所有联系电话列表(数组, 多个电话全部列出)"),
    ("addresses", "所有办公地址列表(数组, 多个地址全部列出)"),
]

# 查询模板: (后缀, 用途)
_QUERY_TEMPLATES = [
    (" 联系人 联系电话 办公地址", "联系方式"),
    (" 法定代表人 注册资本 企业类型 工商信息", "工商信息"),
    (" 成立日期 经营范围 登记机关", "工商信息2"),
    (" 官网 公司简介", "简介"),
    (" 中标 成交 公告", "招标"),
]


def build_queries(unit_name: str) -> list:
    """查询重构: 生成多组查询词(加引号锁定全名)。"""
    qs = []
    for suffix, _use in _QUERY_TEMPLATES:
        qs.append(f'"{unit_name}"{suffix}')
    return qs


def judge_relevant(unit_name: str, title: str, snippet: str) -> bool:
    """LLM 判断搜索结果条目是否与目标单位相关(防止「凤凰县住建局」等误抓)。

    返回 False 表示明确不相关; 无法判断/LLM 不可用时按「含单位名」兜底。
    """
    if not snippet and not title:
        return False
    if unit_name in title:
        return True
    prompt = (
        "判断下面的搜索结果是关于【{unit}】这家单位本身的信息(联系方式/地址/法人/简介/官网/该单位的公告)，"
        "还是只是碰巧提到该单位(招标代理转载、新闻提及、同名词条等)。\n"
        "只输出 JSON: {{\"relevant\": true或false, \"reason\": \"一句话\"}}\n\n"
        f"标题：{title}\n摘要：{snippet[:400]}"
    ).format(unit=unit_name)
    try:
        out = _extract_json(_generate(prompt, timeout=60))
        relevant = out.get("relevant")
        if isinstance(relevant, bool):
            return relevant
        if isinstance(relevant, str):
            return relevant.strip().lower() in ("true", "是", "相关", "1")
    except LLMUnavailable:
        pass
    # 兜底: 完整单位名或核心名(去省市县前缀)在标题里
    core = re.sub(r"^(?:[\u4e00-\u9fa5]{2,6}(?:省|市|县|区|自治区|自治州|地区|旗|州))", "", unit_name).strip()
    return unit_name in title or (len(core) >= 4 and core in title)


def extract_info(unit_name: str, text: str) -> dict:
    """LLM 从文本(搜索结果/正文)结构化抽取单位信息。

    返回 {contact, address, legal_rep, email, website, summary, _source}
    任何字段缺失 → 空字符串; 不编造(正文不存在则为空)。
    """
    if not text:
        return {}
    fields_desc = "、".join(f"{k}({v})" for k, v in _EXTRACT_FIELDS)
    prompt = (
        "你是信息抽取助手。从下面的文本中提取【{unit}】这家单位的联系信息，"
        f"只输出 JSON，字段：{fields_desc}\n"
        "规则：文本中明确出现才填；不存在/不确定的字段一律输出空字符串；"
        "电话只取座机/公司电话，不取招标代理经办人或个人手机；地址取完整办公地址；"
        "绝不编造。\n\n"
        f"文本：\n{text[:4000]}"
    ).format(unit=unit_name)
    try:
        out = _extract_json(_generate(prompt, timeout=120))
    except LLMUnavailable:
        logger.warning("ollama 不可用, LLM 抽取跳过")
        return {}
    clean = {}
    for k, _v in _EXTRACT_FIELDS:
        raw = out.get(k)
        # 多值数组字段: 支持 LLM 输出列表或「a / b / c」分隔文本, 归一化为列表
        if k in ("phones", "addresses"):
            vals = []
            if isinstance(raw, list):
                vals = [str(v).strip() for v in raw if str(v).strip()]
            elif isinstance(raw, str):
                vals = [v.strip() for v in re.split(r"[/；;、\n]", raw) if v.strip()]
            clean[k] = vals
            continue
        val = str(raw or "").strip()
        if val.lower() in ("none", "null", "nan", "/", "-"):
            val = ""
        # 电话字段清理: 去掉「电话：」「联系电话:」前缀
        if k in ("contact", "contact_phone", "fax"):
            val = re.sub(r"^(?:联系电话|电话|公司电话|办公电话|座机|传真)[:：]?\s*", "", val).strip()
        clean[k] = val
    # 若 LLM 没输出多值数组, 但单值字段含多个(「/」分隔), 自动拆出
    if not clean.get("phones") and clean.get("contact_phone"):
        parts = [p.strip() for p in re.split(r"[/；;、\n]", clean["contact_phone"]) if p.strip()]
        if len(parts) > 1:
            clean["phones"] = parts
            clean["contact_phone"] = parts[0]
    if not clean.get("addresses") and clean.get("address"):
        parts = [p.strip() for p in re.split(r"[/；;、\n]", clean["address"]) if p.strip()]
        if len(parts) > 1:
            clean["addresses"] = parts
            clean["address"] = parts[0]
    clean["_source"] = "llm"
    return clean


def _is_blank(v) -> bool:
    """字段是否有真实值: 空字符串 / None / 占位符(/, -, 无等) 都视为空白。"""
    if v is None:
        return True
    s = str(v).strip()
    return s.lower() in {"", "/", "-", "—", "无", "暂无", "null", "none", "nan"}


# 映射: LLM 字段 → company 存储位置。
# column: 公司列; ext: ext_attrs(优先), 字段不在 field_metadata 时自动动态创建。
_MERGE_MAPPING = {
    "province": "column:province",
    "city": "column:city",
    "address": "column:address",
    "legal_rep": "ext:legal_rep",
    "econ_kind": "ext:econ_kind",
    "registered_capital": "ext:registered_capital",
    "belong_org": "ext:belong_org",
    "business_scope": "ext:business_scope",
    "contact_person": "ext:contact_person",
    "contact_phone": "ext:contact_phone",
    "fax": "ext:fax",
    "email": "ext:contact_email",
    "website": "ext:website",
    "postal_code": "ext:postal_code",
    "office_hours": "ext:office_hours",
    "establish_date": "ext:establish_date",
    "oper_status": "ext:oper_status",
    "reg_no": "ext:reg_no",
    "contact": "ext:contact",
    "summary": "ext:summary",
    "credit_code": "column:credit_code",
    "industry": "column:industry",
}


def merge_llm_to_company(db, company, llm: dict) -> list:
    """把 LLM 抽取结果并入 company(只填空字段), 返回更新字段列表。

    省份/城市/地址 → company 列; 其余 → ext_attrs。
    传真/邮编/办公时间等新字段不存在于 field_metadata 时自动动态创建并保存。
    多电话/多地址: contact_phone/address 存主值, phones/addresses 全量存 ext.extra_contacts。
    """
    from app.services.company_field_registry import ensure_company_field

    updated = []
    created_fields: list = []
    ext = dict(company.ext_attrs or {})
    for k, target in _MERGE_MAPPING.items():
        val = (llm.get(k) or "").strip()
        if not val or val.lower() in ("none", "null", "nan", "/", "-"):
            continue
        if k == "registered_capital":
            m = re.search(r"\d+(?:\.\d+)?", val)
            val = m.group(0) if m else ""
            if not val:
                continue
        if k == "establish_date":
            m = re.search(r"\d{4}-\d{1,2}-\d{1,2}", val)
            if not m:
                continue
            val = m.group(0)
        if target.startswith("column:"):
            col = target.split(":")[1]
            if _is_blank(getattr(company, col, None)):
                setattr(company, col, val)
                updated.append(col)
        else:
            field = target.split(":")[1]
            if _is_blank(ext.get(field)):
                # 新字段(传真/邮编/办公时间等)自动注册, 使前端可见
                if field not in _EXISTING_KNOWN_FIELDS and ensure_company_field(db, field):
                    created_fields.append(field)
                ext[field] = val
                updated.append(target)
    # 多联系方式全保留: phones/addresses 列表存 extra_contacts, 供前端选择主要
    extra_contacts = list(ext.get("extra_contacts") or [])
    phones = [p for p in (llm.get("phones") or []) if p.strip()]
    addresses = [a for a in (llm.get("addresses") or []) if a.strip()]
    changed_extra = False
    for p in phones:
        if p not in extra_contacts:
            extra_contacts.append(p)
            changed_extra = True
    for a in addresses:
        if a not in extra_contacts:
            extra_contacts.append(a)
            changed_extra = True
    if changed_extra:
        ext["extra_contacts"] = extra_contacts
        updated.append("ext:extra_contacts")
    if ext:
        company.ext_attrs = ext
    return updated, created_fields


# 已在 field_metadata 中预设的 company 字段(无需动态创建)
_EXISTING_KNOWN_FIELDS = {
    "legal_rep", "econ_kind", "registered_capital", "belong_org", "business_scope",
    "contact_person", "contact_phone", "establish_date", "oper_status", "reg_no",
    "contact", "contact_email", "website", "summary",
}
