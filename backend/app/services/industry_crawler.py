"""行业数据采集管道 — 政务公示/招投标 → qualification/honor/credit_record/bid_open_record。

对应指导文档: docs/gmi-renovation-guide.md A1 / B2

数据源配置: web_source 中 scrape_mode='industry' 的来源。
  - description 首行约定 `kind=credit|honor|qualification`, 决定详情落库到哪张表
  - keywords(逗号分隔) 作为企业名称额外关键词(正文企业名提取的补充)
  - regions 限定地域(逗号分隔)

落库路由:
  - kind=credit      → credit_record       (政务诚信公示/双随机一公开)
  - kind=honor       → honor               (荣誉/评优/表彰公示)
  - kind=qualification → qualification     (资质核准/公告公示)

企业匹配: 复用 intent_crawler._match_unit_to_company(规范化名称模糊匹配 company 库)。
去重: 以 source_url 唯一, 同 URL 已入库则跳过。
四库一平台(需 JS 签名逆向)与工商/司法(企查查供应商 API)不在本模块实现, 见文档 B2。
"""
import logging
import re
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

import httpx

from app.models.web_source import WebSource
from app.models.industry_data import Qualification, Honor, CreditRecord
from app.services.intent_crawler import (
    _extract_detail_links, _extract_title, _extract_body_text,
    _parse_publish_date, _parse_dept, _match_unit_to_company,
)

logger = logging.getLogger("industry_crawler")

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def _fetch(url: str, timeout: int = 15) -> Optional[str]:
    """抓取列表/详情页(政务站点证书链不规范, verify=False)。"""
    try:
        r = httpx.get(url, headers={"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9"},
                      timeout=timeout, follow_redirects=True, verify=False)
        if r.status_code == 200:
            return r.text
    except Exception as e:  # noqa: BLE001
        logger.warning("抓取失败 %s: %s", url, e)
    return None

# 企业名称提取: 常见工商尾缀(有限/股份/集团), 最少 4 字核心名
_COMPANY_NAME_RE = re.compile(
    r"([\u4e00-\u9fa5A-Za-z0-9（）()]{4,80}?"
    r"(?:有限责任公司|股份有限公司|集团有限公司?|有限公司|公司))"
)
# 名称含明显非企业的词缀 → 排除
_COMPANY_BAD_KW = (
    "项目", "标段", "工程名称", "招标编号", "联系方式", "联系人",
    "法定代表人", "资质", "证书", "单位地址", "本次", "范围", "内容",
    "发布日期", "公告", "公示", "发布时间", "中标候选人", "评标委员会",
)


def _extract_company_names(text: str) -> list:
    """从标题+正文提取企业名称(去重保序, 过滤明显非企业短语)。"""
    seen, out = set(), []
    for m in _COMPANY_NAME_RE.finditer(text):
        name = m.group(1).strip()
        # 过滤: 过长(混入句子) / 含非企业词缀 / 纯数字
        if len(name) > 60 or not re.search(r"[\u4e00-\u9fa5]{2,}", name):
            continue
        if any(k in name for k in _COMPANY_BAD_KW):
            continue
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out[:10]


def _source_kind(source: WebSource) -> str:
    """从 source.description 解析 kind, 缺省 credit。"""
    desc = (source.description or "").strip()
    m = re.search(r"kind\s*=\s*(\w+)", desc)
    if m and m.group(1) in ("credit", "honor", "qualification"):
        return m.group(1)
    return "credit"


def _ingest_from_list_page(db: Session, source: WebSource, html: str, kind: str,
                           model, stats: dict, limit: int = 20) -> dict:
    """列表页即数据页模式: 列表页直接含企业名(如矿业权人异常名录), 免抓详情页。

    适用: kyqgs 异常名录等「列表即公示」的源, 详情页有验证码/不必要。
    去重键: (company_id, source), source_url 记录列表页链接(允许多条)。
    """
    text = re.sub(r"\s*\n\s*", "\n", re.sub(r"<[^>]+>", "\n", html))
    title = _extract_title(html) or source.name
    names = _extract_company_names(text)[:limit]
    stats["listed"] = len(names)
    now = datetime.now()
    for name in names:
        try:
            m = _match_unit_to_company(db, name)
            if not m:
                stats["no_company"] += 1
                continue
            exists = db.execute(
                select(model).where(
                    model.company_id == int(m["company_id"]),
                    model.source == source.name[:60],
                    model.is_deleted == False,
                ).limit(1)
            ).scalar_one_or_none()
            if exists:
                stats["skipped"] += 1
                continue
            if kind == "credit":
                db.add(CreditRecord(
                    company_id=int(m["company_id"]), title=title[:500],
                    reason=name[:200], org="自然资源部公示系统",
                    published_at=now, source=source.name[:60], source_url=source.url,
                ))
            else:
                stats["no_company"] += 1
                continue
            stats["stored"] += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("[industry] 列表页入库失败 %s: %s", name, e)
            stats["errors"] += 1
    db.commit()
    return stats


def crawl_industry_source(db: Session, source: WebSource, limit: int = 20) -> dict:
    """抓取单个行业数据源: 列表页 → 详情页 → 企业匹配 → 按 kind 落库。"""
    if not source or not source.url:
        return {"error": "来源无 URL", "source": source.name if source else ""}
    base = re.match(r"(https?://[^/]+)", source.url)
    base_url = base.group(1) if base else source.url
    list_dir = source.url.rpartition("/")[0]
    html = _fetch(source.url)
    if not html:
        return {"error": "列表页抓取失败", "source": source.name}
    links = _extract_detail_links(html, base_url, list_dir=list_dir, limit=limit)
    kind = _source_kind(source)
    model_map = {"credit": CreditRecord, "honor": Honor, "qualification": Qualification}
    model = model_map.get(kind, CreditRecord)
    stats = {"source": source.name, "kind": kind, "listed": len(links),
             "stored": 0, "skipped": 0, "no_company": 0, "errors": 0}
    if not links:
        # 无详情链接 → 列表页直接解析企业名落库(适用异常名录/公示名单)
        return _ingest_from_list_page(db, source, html, kind, model, stats, limit=limit)
    for url in links:
        try:
            existing = db.execute(
                select(model).where(model.source_url == url, model.is_deleted == False).limit(1)
            ).scalar_one_or_none()
            if existing:
                stats["skipped"] += 1
                continue
            detail_html = _fetch(url)
            if not detail_html:
                stats["errors"] += 1
                continue
            title = _extract_title(detail_html)
            body = _extract_body_text(detail_html)
            text = f"{title}\n{body}"
            published = _parse_publish_date(detail_html, text, url) or datetime.now()
            org = _parse_dept(detail_html, body) or "官方公示"
            # 企业匹配: 优先正文企业名, 匹配到 company 库才入库(保证可关联 360°)
            names = _extract_company_names(text)
            matched = False
            for name in names:
                m = _match_unit_to_company(db, name)
                if not m:
                    continue
                company_id = int(m["company_id"])
                if kind == "credit":
                    db.add(CreditRecord(
                        company_id=company_id, title=title[:500], reason=body[:3000],
                        org=org[:250], published_at=published,
                        source=source.name[:60], source_url=url,
                    ))
                elif kind == "honor":
                    db.add(Honor(
                        company_id=company_id, title=title[:500],
                        org=org[:250], honored_at=published.date() if published else None,
                        source=source.name[:60], source_url=url, published_at=published,
                    ))
                else:  # qualification
                    db.add(Qualification(
                        company_id=company_id, category=source.name[:60],
                        level="公示", issue_org=org[:128],
                        source=source.name[:60], source_url=url, published_at=published,
                    ))
                stats["stored"] += 1
                matched = True
                break
            if not matched:
                stats["no_company"] += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("[industry] 详情处理失败 %s: %s", url, e)
            stats["errors"] += 1
    db.commit()
    return stats


def crawl_all_industry_sources(db: Session) -> dict:
    """抓取所有 scrape_mode='industry' 的启用来源。"""
    sources = db.execute(
        select(WebSource).where(
            WebSource.is_deleted == False,
            WebSource.enabled == True,
            WebSource.scrape_mode == "industry",
        )
    ).scalars().all()
    results = [crawl_industry_source(db, s) for s in sources]
    return {"sources": len(sources), "results": results}


def sync_cert_validity(db: Session, expire_days: int = 30) -> dict:
    """刷新 person_cert / qualification 状态: valid_to 过期 → expired, 30天内 → expiring。

    每日调度, 支撑详情页"失效预警"。
    """
    from datetime import timedelta
    from app.models.industry_data import PersonCert
    now = datetime.now().date()
    cut = now + timedelta(days=expire_days)
    updated = 0
    # person_cert
    rows = db.execute(
        select(PersonCert).where(
            PersonCert.is_deleted == False, PersonCert.valid_to.isnot(None)
        )
    ).scalars().all()
    for r in rows:
        new_status = "active"
        if r.valid_to < now:
            new_status = "expired"
        elif r.valid_to <= cut:
            new_status = "expiring"
        if r.status != new_status:
            r.status = new_status
            updated += 1
    # qualification
    qs = db.execute(
        select(Qualification).where(
            Qualification.is_deleted == False, Qualification.valid_to.isnot(None)
        )
    ).scalars().all()
    for r in qs:
        new_status = "active"
        if r.valid_to < now:
            new_status = "expired"
        elif r.valid_to <= cut:
            new_status = "expiring"
        if r.status != new_status:
            r.status = new_status
            updated += 1
    db.commit()
    return {"person_cert": len(rows), "qualification": len(qs), "updated": updated}
