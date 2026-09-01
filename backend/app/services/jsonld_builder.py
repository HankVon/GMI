"""JSON-LD 生成器 — 把内容工厂产物转成 Schema.org 结构化标记。

让 AI 引擎/搜索引擎能「结构化理解」平台产出的内容:
  - company_profile → Organization(实体一致性, 含同义词/地址/业绩链接)
  - faq             → FAQPage(问答题结构化, AI 回答最常引用的格式)
  - industry_report → Dataset(数据报告, AI 偏爱可验证数据)
  - article         → Article(新闻/文章类)
"""
import json
import logging
import re
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger("jsonld")

# 内容类型 → Schema.org 类型
KIND_SCHEMA = {
    "company_profile": "Organization",
    "faq": "FAQPage",
    "industry_report": "Dataset",
    "article": "Article",
}


def _company_org(db: Session, asset) -> Optional[dict]:
    """从平台 company 主数据构建 Organization(实体一致性: 名称/地址/工商信息)。"""
    from app.models.company import Company

    sd = (asset.source_data or {}) if asset else {}
    company = None
    if sd.get("company_id"):
        company = db.get(Company, int(sd["company_id"]))
    if not company:
        return None
    ext = company.ext_attrs or {}
    org = {
        "@type": "Organization",
        "@id": f"https://schema.example.com/org/{company.id}",
        "name": company.name,
        "alternateName": company.short_name or "",
        "description": ext.get("summary") or company.name,
        "address": {
            "@type": "PostalAddress",
            "addressRegion": company.province or "",
            "addressLocality": company.city or "",
            "streetAddress": company.address or "",
        },
    }
    if company.website:
        org["url"] = company.website
    if ext.get("legal_rep"):
        org["founder"] = {"@type": "Person", "name": ext["legal_rep"]}
    if company.industry:
        org["knowsAbout"] = company.industry
    if company.credit_code:
        org["identifier"] = company.credit_code
    return org


def build_organization(db: Session, asset) -> dict:
    """Organization 结构化标记(优先取平台 company 主数据保证实体一致)。"""
    from app.models.company import Company

    sd = asset.source_data or {}
    company = None
    if sd.get("company_id"):
        company = db.get(Company, int(sd["company_id"]))
    if not company:
        # 兜底: 从品牌词构建最小实体
        name = (sd.get("company_name") or asset.title or "企业").replace(" - 企业档案", "")
        return {"@type": "Organization", "name": name}

    ext = company.ext_attrs or {}
    org: dict = {
        "@type": "Organization",
        "@id": f"https://schema.example.com/org/{company.id}",
        "name": company.name,
    }
    if company.short_name:
        org["alternateName"] = company.short_name
    if ext.get("summary"):
        org["description"] = ext["summary"]
    if company.website:
        org["url"] = company.website
    if company.industry:
        org["knowsAbout"] = company.industry
    if company.credit_code:
        org["identifier"] = company.credit_code
    addr = {}
    if company.province:
        addr["addressRegion"] = company.province
    if company.city:
        addr["addressLocality"] = company.city
    if company.address:
        addr["streetAddress"] = company.address
    if addr:
        addr["@type"] = "PostalAddress"
        org["address"] = addr
    if ext.get("legal_rep"):
        org["founder"] = {"@type": "Person", "name": ext["legal_rep"]}
    # 平台内业绩(中标)作为可验证事实挂到 hasCredential
    sd_bids = sd.get("bids") or []
    if sd_bids:
        org["hasCredential"] = [
            {
                "@type": "EducationalOccupationalCredential",
                "credentialCategory": f"{b.get('role')} - {b.get('title', '')[:60]}",
                "about": b.get("region") or "",
            }
            for b in sd_bids[:6]
        ]
    return org


def build_faq(asset) -> dict:
    """FAQPage: 从 问:/答: 行解析问答对。"""
    lines = (asset.content or "").splitlines()
    pairs = []
    cur_q = ""
    cur_a = ""
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if re.match(r"^问[:：]", s):
            if cur_q and cur_a:
                pairs.append({"q": cur_q, "a": cur_a})
            cur_q = re.sub(r"^问[:：]\s*", "", s)
            cur_a = ""
        elif re.match(r"^答[:：]", s):
            cur_a = re.sub(r"^答[:：]\s*", "", s)
        elif cur_q:
            cur_a += (" " if cur_a else "") + s
    if cur_q and cur_a:
        pairs.append({"q": cur_q, "a": cur_a})
    if not pairs:
        # 降级: 整篇作为一段问答
        pairs = [{"q": asset.title, "a": (asset.content or "")[:200]}]
    return {
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": p["q"], "acceptedAnswer": {"@type": "Answer", "text": p["a"][:500]}}
            for p in pairs[:20]
        ],
    }


def build_dataset(asset) -> dict:
    """Dataset: 行业数据报告的统计数据集(可验证数据 → AI 引用友好)。"""
    sd = asset.source_data or {}
    desc = asset.summary or asset.title
    if sd.get("bids") and sd["bids"].get("total") is not None:
        desc = f"{desc} 数据窗内共 {sd['bids']['total']} 条中标、{sd.get('intents', {}).get('total', 0)} 条意向。"
    ds: dict = {
        "@type": "Dataset",
        "name": asset.title,
        "description": desc,
        "datePublished": (asset.published_at or asset.created_at).strftime("%Y-%m-%d"),
        "creator": {"@type": "Organization", "name": asset.created_by_name or "SSM 营销智能体"},
    }
    # 统计字段 → variableMeasured
    measured = []
    bids = sd.get("bids") or {}
    intents = sd.get("intents") or {}
    if bids.get("total") is not None:
        measured.append({"@type": "PropertyValue", "name": "中标公告数", "value": bids["total"]})
    if intents.get("total") is not None:
        measured.append({"@type": "PropertyValue", "name": "意向项目数", "value": intents["total"]})
    if intents.get("amount_sum"):
        measured.append({"@type": "PropertyValue", "name": "意向预算合计(万元)", "value": intents["amount_sum"]})
    if measured:
        ds["variableMeasured"] = measured
    return ds


def build_article(asset) -> dict:
    """Article: 通用文章。"""
    return {
        "@type": "Article",
        "headline": asset.title,
        "description": asset.summary or "",
        "datePublished": (asset.published_at or asset.created_at).strftime("%Y-%m-%d"),
        "author": {"@type": "Organization", "name": asset.created_by_name or "SSM 营销智能体"},
        "articleBody": (asset.content or "")[:5000],
    }


def build_jsonld(db: Session, asset) -> dict:
    """按内容类型生成 JSON-LD(带 @context)。"""
    schema_type = KIND_SCHEMA.get(asset.kind, "Article")
    if schema_type == "Organization":
        body = build_organization(db, asset)
    elif schema_type == "FAQPage":
        body = build_faq(asset)
    elif schema_type == "Dataset":
        body = build_dataset(asset)
    else:
        body = build_article(asset)
    return {"@context": "https://schema.org", **body}


def build_jsonld_pretty(db: Session, asset) -> str:
    """生成可粘贴到网页 <script type="application/ld+json"> 的字符串。"""
    return json.dumps(build_jsonld(db, asset), ensure_ascii=False, indent=2)
