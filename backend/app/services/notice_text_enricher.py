"""公告正文清洗与字段补抽。

设计原则(与前台"不编造数据"约定一致):
  1. 只从正文里抽**有明确标签锚点**的标量字段, 抽不到返回 None, 调用方保持"未披露";
  2. 表格类内容(如"主要标的信息")在源站是连排文本, 无可靠分隔符, 不做猜测性切分;
  3. 金额/得分等数值必须与已有结构化数据(meta.suppliers)交叉校验, 校验不通过则丢弃。

当前已在标讯 383(中标公告) / 405(更正公告) 的真实正文上验证。
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Optional

# ---------------------------------------------------------------- 正文清洗

# 源站 CSS / JS / 备案信息噪声。实测 383、405 正文各命中约 9 处。
_NOISE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # 整行的 CSS 选择器(含逗号选择器 .a,.b{} 与 @media 嵌套), 需在裸选择器规则之前执行
    (re.compile(r"^[.@#][^{}\n]*\{[^}]*\}(?:[ \t]*/\*.*?\*/)?\s*$", re.M), ""),
    (re.compile(r"\.[a-zA-Z_][\w-]*\s*\{[^}]*\}", re.S), ""),          # .copyright_bl{...}
    (re.compile(r"@media[^{]*\{(?:[^{}]|\{[^}]*\})*\}", re.S), ""),    # @media print{...}
    (re.compile(r"^\s*//.*$", re.M), ""),                              # //document.getElementById...
    (re.compile(r"var\s+\w+\s*=[\s\S]*?;", re.S), ""),                 # var myDate = new Date();
    (re.compile(r"\$\([^)]*\)\.[a-zA-Z]+\([^)]*\);", re.S), ""),       # $("#botm_cpy").html(...)
    (re.compile(r"主办单位：[^\n]*", re.S), ""),
    (re.compile(r"网站标识码：[^\n]*", re.S), ""),
    (re.compile(r"京ICP备[^\n]*", re.S), ""),
    (re.compile(r"©\s*\d{4}\s*-\s*[^\n]*", re.S), ""),
]


def clean_body(raw: Optional[str]) -> str:
    """去除源站 CSS/JS/备案噪声, 保留正文段落结构。"""
    text = str(raw or "")
    for pattern, repl in _NOISE_PATTERNS:
        text = pattern.sub(repl, text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------- 归一化

def parse_cn_datetime(value: Optional[str]) -> Optional[datetime]:
    """'2026年08月28日 22:02' / '2026年08月28日' / '2026年09月14日11时00分' -> datetime。"""
    if not value:
        return None
    m = re.search(
        r"(\d{4})年(\d{1,2})月(\d{1,2})日"
        r"(?:\s*(\d{1,2})[:：时]?\s*(\d{1,2})分?)?",
        str(value),
    )
    if not m:
        return None
    year, month, day, hour, minute = m.groups()
    try:
        return datetime(int(year), int(month), int(day), int(hour or 0), int(minute or 0))
    except ValueError:
        return None


def fmt_dt(dt: Optional[datetime], with_time: bool = False) -> Optional[str]:
    if not dt:
        return None
    return dt.strftime("%Y-%m-%d %H:%M") if with_time else dt.strftime("%Y-%m-%d")


_EPOCH = date(1899, 12, 30)


def excel_serial_to_date(value: Any) -> Optional[str]:
    """Excel 日期序列号 -> ISO 日期。仅处理落在合理区间的纯数字, 避免误伤编号列。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not 20000 < number < 80000:
        return None
    return (_EPOCH + timedelta(days=int(number))).isoformat()


# ---------------------------------------------------------------- 标量抽取

_RULES: dict[str, re.Pattern[str]] = {
    "project_code":       re.compile(r"项目编号[:：]\s*([^\n]+)"),
    "project_name":       re.compile(r"项目名称[:：]\s*([^\n]+)"),
    "admin_region":       re.compile(r"行政区域\s*([\s\S]{2,40}?)(?=公告时间)"),
    "announced_at":       re.compile(r"公告时间\s*(\d{4}年\d{1,2}月\d{1,2}日\s*\d{2}:\d{2})"),
    "first_published_at": re.compile(r"首次公告日期[:：]\s*(\d{4}年\d{1,2}月\d{1,2}日)"),
    "corrected_at":       re.compile(r"更正日期[:：]\s*(\d{4}年\d{1,2}月\d{1,2}日)"),
    "correction_scope":   re.compile(r"更正事项[:：]\s*([^\n]+)"),
    "agency_name":        re.compile(r"代理机构名称\s*([^\n]+)"),
    "agency_address":     re.compile(r"代理机构地址\s*([^\n]+)"),
    "agency_phone":       re.compile(r"代理机构联系方式\s*([^\n]+)"),
    "purchaser_address":  re.compile(r"采购单位地址\s*([^\n]+)"),
    "purchaser_phone":    re.compile(r"采购单位联系方式\s*([^\n]+)"),
    "project_person":     re.compile(r"项目联系人\s*([^\n]+)"),
    "project_phone":      re.compile(r"项目联系电话\s*([^\n]+)"),
    "total_amount_text":  re.compile(r"总中标金额\s*([^\n]+)"),
    "expert_list":        re.compile(r"评审专家名单\s*([^\n]+)"),
    "agency_fee_standard": re.compile(r"代理服务收费标准[:：]\s*([^\n]+)"),
    "agency_fee_amount":  re.compile(r"代理服务收费金额（元）[:：]\s*([^\n]+)"),
    "announce_period":    re.compile(r"公告期限\s*\n?\s*([^\n]+)"),
    "supplement":         re.compile(r"其他补充事宜\s*\n?\s*([^\n]+)"),
    "build_scale":        re.compile(r"总建筑面积\s*([\d,.]+\s*㎡?)"),
    "service_term":       re.compile(r"(期限[一二三四五六七八九十两半\d]+[年月][^\n，。]{0,30})"),
}

# 监督部门信息只在"同级政府采购监督管理部门"章节内抽取,
# 否则会误命中采购人自己的"地 址/联系方式"(实测 383 即出现该问题)。
_SUPERVISOR_SECTION_RE = re.compile(
    r"同级政府采购监督管理部门\s*:?\s*\n([\s\S]{0,400}?)(?=\n相关公告|\n\.[a-zA-Z_]|\Z)"
)
_SUPERVISOR_FIELDS = {
    "supervisor_name":    re.compile(r"名\s*称[:：]\s*([^\n]+)"),
    "supervisor_address": re.compile(r"地\s*址[:：]\s*([^\n]+)"),
    "supervisor_fax":     re.compile(r"传\s*真[:：]\s*([^\n]+)"),
    "supervisor_phone":   re.compile(r"监督投诉电话[:：]?\s*([\d\-（）()]+)"),
}


def extract_supervisor(cleaned: str) -> dict[str, Optional[str]]:
    """抽取同级政府采购监督管理部门信息; 无该章节时全部返回 None。"""
    out = {key: None for key in _SUPERVISOR_FIELDS}
    m = _SUPERVISOR_SECTION_RE.search(cleaned)
    if not m:
        return out
    section = m.group(1)
    for key, pattern in _SUPERVISOR_FIELDS.items():
        found = pattern.search(section)
        if found:
            out[key] = found.group(1).strip().strip(_STRIP_CHARS) or None
    return out

# 需要归一化为日期的字段
_DATE_FIELDS = {"first_published_at", "corrected_at"}
_DATETIME_FIELDS = {"announced_at"}

# 需要清洗首尾冒号/空白的字段
_STRIP_CHARS = "：: \t　"


def extract_scalars(cleaned: str) -> dict[str, Any]:
    """抽取有明确标签锚点的标量字段; 未命中一律 None。"""
    out: dict[str, Any] = {}
    for key, pattern in _RULES.items():
        m = pattern.search(cleaned)
        if not m:
            out[key] = None
            continue
        raw = (m.group(1) or "").strip().strip(_STRIP_CHARS)
        if not raw:
            out[key] = None
        elif key in _DATETIME_FIELDS:
            out[key] = fmt_dt(parse_cn_datetime(raw), with_time=True)
        elif key in _DATE_FIELDS:
            out[key] = fmt_dt(parse_cn_datetime(raw))
        elif key == "correction_scope":
            out[key] = [x.strip() for x in re.split(r"[,，、]", raw) if x.strip()]
        elif key == "expert_list":
            out[key] = [x.strip() for x in re.split(r"[,，、]", raw) if x.strip()]
        else:
            out[key] = raw
    out.update(extract_supervisor(cleaned))
    return out


# ---------------------------------------------------------------- 时间节点

_TIME_RE = re.compile(r"\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}时\d{1,2}分")


def extract_deadlines(cleaned: str) -> dict[str, Optional[str]]:
    """抽取投标截止/开标时间。

    更正类公告正文里会同时出现"更正前"和"更正后"两个时间,
    取**最后一个**作为生效值(实测 405: 09月02日11时30分 -> 09月14日11时00分)。
    """
    hits = [parse_cn_datetime(x) for x in _TIME_RE.findall(cleaned)]
    hits = [d for d in hits if d]
    return {
        "prev_bid_deadline": fmt_dt(hits[-2], with_time=True) if len(hits) >= 2 else None,
        "bid_deadline": fmt_dt(hits[-1], with_time=True) if hits else None,
        "opening_time": fmt_dt(hits[-1], with_time=True) if hits else None,
    }


# ---------------------------------------------------------------- 中标结果

_ROW_RE = re.compile(r"报价[:：]\s*([\d,]+(?:\.\d+)?)\s*（元）\s*([\d.]+)")


def extract_award(cleaned: str, known: Optional[list[dict]] = None) -> dict[str, Any]:
    """抽取中标金额/评审总得分, 并与已知结构化供应商数据交叉校验。

    仅在能校验通过(或确实无已知数据可做参照)时才返回, 避免从连排文本里臆造。
    """
    result: dict[str, Any] = {"amount": None, "score": None, "amount_text": None}
    m = _ROW_RE.search(cleaned)
    if not m:
        return result
    try:
        amount = float(m.group(1).replace(",", ""))
        score = float(m.group(2))
    except ValueError:
        return result

    known_amounts: list[float] = []
    for item in known or []:
        try:
            known_amounts.append(float(str(item.get("amount")).replace(",", "")))
        except (TypeError, ValueError):
            continue
    # 有参照时必须一致才采信(容差 1 元)
    if known_amounts and not any(abs(amount - k) < 1 for k in known_amounts):
        return result

    result["amount"] = amount
    result["score"] = score
    return result


# ---------------------------------------------------------------- 更正内容

_CORRECTION_SECTION_RE = re.compile(
    r"更正内容[:：]\s*\n([\s\S]{0,3000}?)(?=\n更正日期|\n三、|\n四、|\Z)"
)
_CORRECTION_SPLIT_RE = re.compile(r"^\s*(\d{1,2})\s*(?=\S)", re.M)


def extract_corrections(cleaned: str) -> list[dict[str, Any]]:
    """抽取"更正内容"表格行(序号/更正项/更正前/更正后)。

    约束(避免把正文里的导航序号 "1.采购人信息" 之类误判为更正项):
      1. 必须存在"更正内容:"章节, 否则返回空列表;
      2. 在章节内按行首序号切块, 块内保留原文 raw, 不做跨行合并的猜测;
      3. 仅在能明确切出"更正前/更正后"两段时才填这两列, 否则置 None。
    """
    section_match = _CORRECTION_SECTION_RE.search(cleaned)
    if not section_match:
        return []
    section = section_match.group(1)

    blocks: list[tuple[int, str]] = []
    last_end = 0
    matches = list(_CORRECTION_SPLIT_RE.finditer(section))
    for idx, m in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(section)
        blocks.append((int(m.group(1)), section[m.end():end].strip()))
        last_end = end
    if not blocks:
        return []

    rows: list[dict[str, Any]] = []
    for no, raw in blocks:
        if len(raw) < 4:
            continue
        item, before, after = raw, None, None
        parts = re.split(r"(?=本项目为|更正后[:：])", raw)
        if len(parts) >= 3:
            item, before, after = parts[0].strip(), parts[1].strip(), parts[2].strip()
        elif len(parts) == 2:
            item, before = parts[0].strip(), parts[1].strip()
        rows.append({"no": no, "item": item, "before": before, "after": after, "raw": raw})
    return rows


# ---------------------------------------------------------------- 附件信息

_ATTACHMENT_RE = re.compile(r"附件信息[:：]\s*\n([\s\S]{0,600}?)(?=\n相关公告|\n\.[a-zA-Z_]|\Z)")


def extract_attachment_hints(cleaned: str) -> list[dict[str, str]]:
    """从正文"附件信息"段落提取附件名 + 大小。

    采集器常常只抓到文字没抓到下载链接(实测 383 即为此情况),
    这里至少把"有哪些附件、多大"披露出来, 下载链接缺失时前端显示为纯文本。
    """
    m = _ATTACHMENT_RE.search(cleaned)
    if not m:
        return []
    lines = [x.strip() for x in m.group(1).splitlines() if x.strip()]
    hints: list[dict[str, str]] = []
    for i in range(0, len(lines) - 1):
        name, size = lines[i], lines[i + 1]
        if re.fullmatch(r"[\d.]+\s*[KMG]B?", size, re.I):
            hints.append({"name": name, "size": size, "url": None})
            i += 1
    return hints


# ---------------------------------------------------------------- 统一入口

def enrich(notice_meta: dict[str, Any]) -> dict[str, Any]:
    """对单条公告的 meta 做清洗 + 补抽, 返回可下发的结构化补充段。

    只做补充, 不覆盖已有结构化数据: 调用方按需取用。
    """
    cleaned = clean_body(notice_meta.get("body") or notice_meta.get("content") or "")
    if not cleaned:
        return {"body_clean": "", "scalars": {}, "deadlines": {}, "award": {},
                "corrections": [], "attachment_hints": []}

    suppliers = notice_meta.get("suppliers") or []
    return {
        "body_clean": cleaned,
        "scalars": extract_scalars(cleaned),
        "deadlines": extract_deadlines(cleaned),
        "award": extract_award(cleaned, suppliers if isinstance(suppliers, list) else []),
        "corrections": extract_corrections(cleaned),
        "attachment_hints": extract_attachment_hints(cleaned),
    }
