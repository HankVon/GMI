"""企查查企业信息补全服务

通过企查查开放平台 API 根据企业名称/信用代码查询工商信息，回填 company 表。
鉴权: Token = MD5(key + 时间戳 + 密钥) 转大写, 请求头带 Token 与 Timespan。

使用基础工商详情接口 ECIV4/GetBasicDetailsByName（返回单条企业完整工商信息）。
"""
import hashlib
import re
import time
from typing import Optional
from urllib.parse import quote

import httpx

from app.config import settings


def _get_qcc_config():
    return {
        "key": getattr(settings, "QCC_APP_KEY", "") or "",
        "secret": getattr(settings, "QCC_APP_SECRET", "") or "",
        "url": getattr(settings, "QCC_API_URL", "https://api.qichacha.com/ECIV4/GetBasicDetailsByName"),
    }


def _make_headers(key: str, secret: str) -> dict:
    timespan = str(int(time.time()))
    token = hashlib.md5((key + timespan + secret).encode("utf-8")).hexdigest().upper()
    return {
        "Token": token,
        "Timespan": timespan,
        "User-Agent": "Mozilla/5.0 (compatible; SSM/1.0)",
    }


_PROVINCE_RE = re.compile(r"^(北京|天津|上海|重庆|河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|海南|四川|贵州|云南|陕西|甘肃|青海|台湾|内蒙古|广西|西藏|宁夏|新疆|香港|澳门|广州|深圳)")


def _split_region_from_area(area: dict, address: str) -> tuple[Optional[str], Optional[str]]:
    """优先用结构化 Area 取省市，回退从地址解析"""
    province = None
    city = None
    if isinstance(area, dict):
        province = area.get("Province") or area.get("province")
        city = area.get("City") or area.get("city")
    if not province and address:
        m = _PROVINCE_RE.match(address)
        province = m.group(1) if m else None
        if province:
            rest = address[m.end():]
            cm = re.match(r"([\u4e00-\u9fa5]{2,6}?)(市|自治州|地区|盟)", rest)
            if cm:
                city = cm.group(1) + cm.group(2)
            else:
                cm = re.match(r"([\u4e00-\u9fa5]{2,6}?)(县|区)", rest)
                if cm:
                    city = cm.group(1)
    return province, city


def _truncate_date(value: str) -> Optional[str]:
    """将 '2018-05-16 00:00:00' / '2018-05-16' 截为日期部分"""
    if not value:
        return None
    return str(value).split(" ")[0].split("T")[0]


def _map_qcc_to_company(result: dict) -> dict:
    """企查查 GetBasicDetailsByName 返回（单条）→ company 表字段映射

    返回 {常规字段: {...}, ext: {...}}，ext 写入 ext_attrs 动态字段。
    field_key 需与 field_metadata(entity_type='company') 对齐。
    """
    mapping: dict = {}
    ext: dict = {}

    if result.get("Name"):
        mapping["name"] = result["Name"]
    if result.get("CreditCode"):
        mapping["credit_code"] = result["CreditCode"]
    if result.get("Address"):
        mapping["address"] = result["Address"]
    # 省市：优先结构化 Area，回退地址解析
    province, city = _split_region_from_area(result.get("Area"), result.get("Address", ""))
    if province:
        mapping["province"] = province
    if city:
        mapping["city"] = city

    # 下列字段无独立列，写入 ext_attrs 动态字段（field_key 需与 field_metadata 对齐）
    if result.get("OperName"):
        ext["legal_rep"] = result["OperName"]
    if result.get("StartDate"):
        ext["establish_date"] = _truncate_date(result["StartDate"])
    if result.get("Status"):
        ext["oper_status"] = result["Status"]
    if result.get("No"):
        ext["reg_no"] = result["No"]
    if result.get("EconKind"):
        ext["econ_kind"] = result["EconKind"]
    if result.get("BelongOrg"):
        ext["belong_org"] = result["BelongOrg"]
    if result.get("Scope"):
        ext["business_scope"] = result["Scope"]
    # 注册资本：优先 RegisteredCapital(纯数值/字符串)，回退 RegistCapi
    reg_capi = result.get("RegisteredCapital") or result.get("RegistCapi")
    if reg_capi:
        ext["registered_capital"] = str(reg_capi)

    return {"fields": mapping, "ext": ext}


def _map_verify_to_company(result: dict) -> dict:
    """企查查 EnterpriseInfo/Verify 返回 → company 字段映射(侧重电话/联系方式)。

    Verify 接口需要单独购买; 返回 ContactInfo.Tel / MoreTelList 等联系方式字段。
    返回 {fields: {...}, ext: {...}}, ext 写入 ext_attrs 动态字段。
    """
    ext: dict = {}
    if result.get("OperName"):
        ext["legal_rep"] = result["OperName"]
    ci = result.get("ContactInfo") or {}
    tel = (ci.get("Tel") or "").strip()
    more = [t.get("Tel", "").strip() for t in (ci.get("MoreTelList") or []) if t.get("Tel")]
    phones = [p for p in [tel] + more if p]
    if phones:
        # 去重合并, 座机电话统一存 ext.contact(甲方联系方式)
        seen, merged = set(), []
        for p in phones:
            if p not in seen:
                seen.add(p)
                merged.append(p)
        ext["contact"] = " / ".join(merged)
    if ci.get("Email"):
        ext["contact_email"] = ci["Email"]
    return {"fields": {}, "ext": ext}


async def fetch_company_verify(keyword: str) -> dict:
    """调用企查查企业信息核验接口(需单独购买)获取联系电话。

    返回: {"ok": bool, "result": dict|None, "message": str}
    result 为 VerifyResult==1 时的 Data 对象。
    """
    cfg = _get_qcc_config()
    if not cfg["key"] or not cfg["secret"]:
        return {"ok": False, "result": None, "message": "企查查未配置"}
    url = "https://api.qichacha.com/EnterpriseInfo/Verify"
    headers = _make_headers(cfg["key"], cfg["secret"])
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params={"key": cfg["key"], "searchKey": keyword}, headers=headers)
            data = resp.json()
        if data.get("VerifyResult") == 1 and data.get("Data"):
            return {"ok": True, "result": data["Data"], "message": "ok"}
        msg = data.get("Message") or data.get("Reason") or "企查查核验无结果"
        return {"ok": False, "result": None, "message": f"企查查核验失败: {msg}"}
    except Exception as e:
        return {"ok": False, "result": None, "message": f"请求企查查核验失败: {e}"}


async def fetch_company_info(keyword: str) -> dict:
    """调用企查查详情接口查询企业工商信息

    返回: {"ok": bool, "result": dict|None, "message": str}
    result 为单条企业信息 dict。
    """
    cfg = _get_qcc_config()
    if not cfg["key"] or not cfg["secret"]:
        return {"ok": False, "result": None, "message": "企查查未配置"}

    url = f"{cfg['url']}?key={cfg['key']}&keyword={quote(keyword)}"
    headers = _make_headers(cfg["key"], cfg["secret"])
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            data = resp.json()
        status = str(data.get("Status"))
        if status == "200" and data.get("Result"):
            return {"ok": True, "result": data["Result"], "message": "ok"}
        qcc_msg = data.get("Message") or data.get("Reason") or f"企查查返回Status={status}"
        return {"ok": False, "result": None, "message": f"企查查接口错误: {qcc_msg}"}
    except Exception as e:
        return {"ok": False, "result": None, "message": f"请求企查查失败: {e}"}


async def enrich_company(company) -> dict:
    """补全单个 company 记录，返回 {updated: [field...], source: "qcc"}"""
    if not getattr(settings, "QCC_APP_KEY", "") or not getattr(settings, "QCC_APP_SECRET", ""):
        return {"updated": [], "source": "qcc", "ok": False,
                "message": "企查查未配置(请填写 backend/.env 的 QCC_APP_KEY/QCC_APP_SECRET)"}

    fetch = await fetch_company_info(company.name or company.code)
    if not fetch["ok"]:
        return {"updated": [], "source": "qcc", "ok": False, "message": fetch["message"]}

    mapped = _map_qcc_to_company(fetch["result"])
    updated = []
    for field, value in mapped["fields"].items():
        if value and not getattr(company, field, None):
            setattr(company, field, value)
            updated.append(field)

    # 动态字段补全（ext_attrs）
    if mapped["ext"] and company.ext_attrs is None:
        company.ext_attrs = {}
    for k, v in mapped["ext"].items():
        if v and (not company.ext_attrs or not company.ext_attrs.get(k)):
            company.ext_attrs = dict(company.ext_attrs or {})
            company.ext_attrs[k] = v
            updated.append(f"ext:{k}")

    if not updated:
        return {"updated": [], "source": "qcc", "ok": True,
                "message": "查询成功，但无可补全的空字段(已有信息未覆盖)"}
    return {"updated": updated, "source": "qcc", "ok": True, "message": "ok"}


# ---------------------------------------------------------------------------
# 同步版本: 供项目导入等同步流程直接调用(不依赖事件循环)
# ---------------------------------------------------------------------------


def _apply_mapping(company, mapped: dict) -> list:
    """把映射结果应用到 company(只填空字段), 返回更新的字段名列表。"""
    updated = []
    for field, value in mapped.get("fields", {}).items():
        if value and not getattr(company, field, None):
            setattr(company, field, value)
            updated.append(field)
    ext = mapped.get("ext") or {}
    if ext and company.ext_attrs is None:
        company.ext_attrs = {}
    for k, v in ext.items():
        if v and (not company.ext_attrs or not company.ext_attrs.get(k)):
            company.ext_attrs = dict(company.ext_attrs or {})
            company.ext_attrs[k] = v
            updated.append(f"ext:{k}")
    return updated


def enrich_company_sync(company) -> dict:
    """同步版 enrich_company: 用同步 httpx 调企查查, 返回与 enrich_company 同结构。

    适用场景: 同步导入脚本/后台任务中调用(不依赖事件循环, 无 loop 冲突)。
    只填空字段, 不覆盖已有信息, 查不到的如实返回 message。
    """
    if not getattr(settings, "QCC_APP_KEY", "") or not getattr(settings, "QCC_APP_SECRET", ""):
        return {"updated": [], "source": "qcc", "ok": False,
                "message": "企查查未配置(请填写 backend/.env 的 QCC_APP_KEY/QCC_APP_SECRET)"}

    cfg = _get_qcc_config()
    headers = _make_headers(cfg["key"], cfg["secret"])
    keyword = company.name or company.code
    updated: list = []
    qcc_msg = ""
    try:
        with httpx.Client(timeout=15) as client:
            # 1) 基础工商详情(已购): 法定代表人/地址/信用代码等
            r1 = client.get(f"{cfg['url']}?key={cfg['key']}&keyword={quote(keyword)}", headers=headers)
            d1 = r1.json()
            if str(d1.get("Status")) == "200" and d1.get("Result"):
                updated += _apply_mapping(company, _map_qcc_to_company(d1["Result"]))
            else:
                qcc_msg = d1.get("Message") or d1.get("Reason") or f"Status={d1.get('Status')}"
            # 2) 企业信息核验(电话, 需单独购买; 未购买时忽略不报错)
            r2 = client.get("https://api.qichacha.com/EnterpriseInfo/Verify",
                            params={"key": cfg["key"], "searchKey": keyword}, headers=headers)
            d2 = r2.json()
            if d2.get("VerifyResult") == 1 and d2.get("Data"):
                updated += _apply_mapping(company, _map_verify_to_company(d2["Data"]))
    except Exception as e:  # noqa: BLE001
        return {"updated": updated, "source": "qcc", "ok": False,
                "message": f"请求企查查失败: {e}"}

    if not updated:
        return {"updated": [], "source": "qcc", "ok": True,
                "message": qcc_msg or "查询成功，但无可补全的空字段(已有信息未覆盖)"}
    return {"updated": updated, "source": "qcc", "ok": True, "message": "ok"}
