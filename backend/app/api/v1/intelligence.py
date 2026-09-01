"""情报中心统一检索 — 跨 意向公告/招标线索/中标公告 三源, 按项目阶段+地域(川藏新,省-市-县)+时间 检索。

阶段划分:
  investment  投资意向期  → intent_notice(政务源意向/采购意向)
  bidding     招标期      → web_clue 中招标/采购类公告
  awarded     中标公示期  → bid_notice(中标/成交公告)
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.web_clue import WebClue
from app.models.bid_notice import BidNotice
from app.models.intent_notice import IntentNotice
from app.services.china_regions import extract_target_province

router = APIRouter(prefix="/intelligence", tags=["情报中心"])

# 招标特征词(命中即视为招标期公告)
_BIDDING_KW = ("招标", "采购", "磋商", "竞争性", "询价", "比选", "谈判", "单一来源", "竞价")
# 中标特征词(招标期内排除)
_AWARD_KW = ("中标", "成交")

STAGES = {
    "investment": {"label": "投资意向期", "desc": "政务源采购意向/需求公示/规划公告"},
    "bidding": {"label": "招标期", "desc": "招标/采购公告(已挂网, 可报名参与)"},
    "awarded": {"label": "中标公示期", "desc": "中标/成交公告(成交结果与供应商)"},
}


def _is_bidding_clue(title: str) -> bool:
    """招标期判定: 含招标特征词 且 不含中标词。"""
    t = title or ""
    if any(k in t for k in _AWARD_KW):
        return False
    return any(k in t for k in _BIDDING_KW)


def _target_of(text: str) -> str:
    return extract_target_province(text)


# 公司业务能力关键词(与 intent_crawler._BUSINESS_KEYWORDS 对齐, 用于标注「与哪些公司能力匹配」)
_CAPABILITY_KW = (
    "地质灾害", "地灾", "滑坡", "泥石流", "崩塌", "隐患治理", "排危", "避险搬迁", "边坡治理",
    "生态修复", "生态治理", "矿山修复", "矿山地质", "恢复治理", "水土保持", "水土流失",
    "地质勘察", "地质勘查", "工程勘察", "岩土", "钻探", "监测预警", "地质环境监测", "测绘",
    "地灾评估", "危险性评估", "勘查设计", "勘察设计", "治理工程", "整治",
)


def _capability_of(title: str, region: str = "") -> dict:
    """基于标题+地域, 生成「与公司库能力匹配」标注。

    返回 {matched: bool, keywords: [命中业务词], companies: [匹配的公司名]}
    匹配规则:
      1) 标题命中业务能力关键词 → 标记可匹配
      2) 地域(川藏新)与目标省份一致 → 地域可匹配
      3) 公司库中 company_type/行业 含命中关键词的公司 → 列出
    """
    hits = [k for k in _CAPABILITY_KW if k in (title or "")]
    if not hits:
        return {"matched": False, "keywords": [], "companies": []}
    from app.models.company import Company
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        matched_companies = []
        for c in db.execute(
            select(Company).where(Company.is_deleted == False).limit(500)
        ).scalars().all():
            ctype = c.company_type or ""
            name = c.name or ""
            if any(k in ctype or k in name for k in hits[:3]):
                matched_companies.append(c.name)
                if len(matched_companies) >= 5:
                    break
        return {"matched": True, "keywords": hits[:4], "companies": matched_companies}
    finally:
        db.close()


@router.get("/search")
async def intelligence_search(
    stage: Optional[str] = Query(None, description="阶段 investment/bidding/awarded, 缺省全部"),
    province: Optional[str] = Query(None, description="省核心词(四川/西藏/新疆)"),
    city: Optional[str] = Query(None, description="市核心词(成都/日喀则/喀什)"),
    county: Optional[str] = Query(None, description="县核心词(喜德/普兰/定日)"),
    keyword: Optional[str] = Query(None, description="标题模糊搜索"),
    days: Optional[int] = Query(365, description="时间窗(近N天)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """统一情报检索(按阶段/地域三级/关键词/时间)。"""
    cutoff = datetime.now() - timedelta(days=days or 0)
    items: list[dict] = []

    want = {s: (not stage or stage == s) for s in STAGES}

    # 1) 投资意向期
    if want["investment"]:
        stmt = select(IntentNotice).where(IntentNotice.is_deleted == False)
        if keyword:
            stmt = stmt.where(IntentNotice.title.contains(keyword))
        if days:
            stmt = stmt.where(IntentNotice.published_at >= cutoff)
        for it in db.execute(stmt.order_by(IntentNotice.published_at.desc())).scalars().all():
            text_pool = f"{it.title or ''} {it.region or ''}"
            if province and (it.province or _target_of(text_pool)) != province:
                continue
            if city and city not in text_pool:
                continue
            if county and county not in text_pool:
                continue
            items.append({
                "id": it.id, "stage": "investment", "stage_label": STAGES["investment"]["label"],
                "title": it.title, "url": it.url or "",
                "province": it.province or _target_of(text_pool) or "",
                "city": it.city or "", "county": it.county or "",
                "region": it.region or "",
                "published_at": it.published_at.strftime("%Y-%m-%d %H:%M") if it.published_at else "",
                "source_name": it.dept or "政务源",
                "purchaser": it.dept or "", "amount": str(it.amount or "") + "万" if it.amount else "",
                "summary": it.raw_text or "",
                "capability": _capability_of(it.title or "", it.region or ""),
            })

    # 2) 招标期
    if want["bidding"]:
        stmt = select(WebClue).where(WebClue.is_deleted == False, WebClue.status == "accepted")
        if keyword:
            stmt = stmt.where(or_(WebClue.title.contains(keyword), WebClue.summary.like(f"%{keyword}%")))
        if days:
            stmt = stmt.where(WebClue.published_at >= cutoff)
        for c in db.execute(stmt.order_by(WebClue.published_at.desc())).scalars().all():
            if not _is_bidding_clue(c.title or ""):
                continue
            meta = c.meta if isinstance(c.meta, dict) else {}
            text_pool = " ".join([c.title or "", c.region or "", meta.get("regionName") or "",
                                  meta.get("regionName_") or "", meta.get("purchaserAddr") or ""])
            tgt = _target_of(text_pool)
            if province and tgt != province:
                continue
            if city and city not in text_pool:
                continue
            if county and county not in text_pool:
                continue
            if not tgt:
                continue  # 非川藏新公告不展示
            items.append({
                "id": c.id, "stage": "bidding", "stage_label": STAGES["bidding"]["label"],
                "title": c.title, "url": c.url or "",
                "province": tgt, "city": "", "county": "",
                "region": c.region or meta.get("regionName") or tgt,
                "published_at": c.published_at.strftime("%Y-%m-%d %H:%M") if c.published_at else "",
                "source_name": c.source_name or "网页线索",
                "purchaser": meta.get("purchaser") or "", "amount": meta.get("budget") or "",
                "summary": (c.content or c.summary or "")[:300],
            })

    # 3) 中标公示期
    if want["awarded"]:
        # 数据范围过滤(复用 bid 对象级授权; 未启用/无对象授权时保持现状)
        from app.services.data_scope_service import resolve_scope, scope_filter
        _scope = resolve_scope(db, user, "bid")
        _cond = scope_filter(_scope, BidNotice, "bid")
        stmt = select(BidNotice).where(BidNotice.is_deleted == False)
        if _cond is not None:
            stmt = stmt.where(_cond)
        if keyword:
            stmt = stmt.where(BidNotice.title.contains(keyword))
        if days:
            stmt = stmt.where(BidNotice.published_at >= cutoff)
        for bn in db.execute(stmt.order_by(BidNotice.published_at.desc())).scalars().all():
            text_pool = f"{bn.purchaser or ''} {bn.title or ''}"
            tgt = _target_of(text_pool)
            if province and (tgt or bn.region) != province:
                continue
            if not tgt and not (bn.region and province == bn.region):
                if province:
                    continue
            if not tgt and not bn.region:
                continue  # 无地域信息不展示
            if city and city not in text_pool:
                continue
            if county and county not in text_pool:
                continue
            suppliers = ", ".join([s.get("supplier", "") for s in (bn.meta or {}).get("suppliers", []) if s.get("supplier")])
            items.append({
                "id": bn.id, "stage": "awarded", "stage_label": STAGES["awarded"]["label"],
                "title": bn.title, "url": bn.url or "",
                "province": tgt or bn.region or "", "city": "", "county": "",
                "region": bn.region or "",
                "published_at": bn.published_at.strftime("%Y-%m-%d %H:%M") if bn.published_at else "",
                "source_name": bn.source_name or "中标公告",
                "purchaser": bn.purchaser or "", "amount": "",
                "summary": f"中标供应商: {suppliers}" if suppliers else "",
            })

    # 排序 + 分页
    items.sort(key=lambda x: x["published_at"] or "", reverse=True)
    total = len(items)
    paged = items[(page - 1) * page_size: page * page_size]
    return {
        "success": True,
        "total": total,
        "items": paged,
        "stages": [{"value": k, "label": v["label"], "desc": v["desc"]} for k, v in STAGES.items()],
        "filters": {"stage": stage or "all", "province": province or "", "city": city or "", "county": county or ""},
    }
