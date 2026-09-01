"""可演进的招投标组合检索 API。

默认走当前 MySQL 数据源；配置 ES_URL 后可切换到 search_after 检索。
本模块不包含会员/VIP 逻辑，导出和下载仍由现有登录权限控制。
"""
from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.bid_notice import BidNotice
from app.models.subscription_task import SubscriptionTask
from app.services.tender_search import search_es

router = APIRouter(prefix="/tenders", tags=["招投标组合检索"])


def _fallback_query(payload: dict[str, Any], db: Session) -> dict[str, Any]:
    stmt = select(BidNotice).where(BidNotice.is_deleted == False)
    keyword = str(payload.get("keyword") or "").strip()
    if keyword:
        stmt = stmt.where(BidNotice.title.contains(keyword))
    for condition in payload.get("filters", []):
        if not isinstance(condition, dict) or not condition.get("value"): continue
        field, value = condition.get("field"), condition.get("value")
        if field == "province": stmt = stmt.where(BidNotice.region == value)
        elif field == "notice_type": stmt = stmt.where(BidNotice.notice_type.contains(str(value)))
        elif field == "purchaser": stmt = stmt.where(BidNotice.purchaser.contains(str(value)))
    tree = payload.get("condition_tree")
    if isinstance(tree, dict):
        # MySQL fallback保守处理叶子条件；复杂 AND/OR 交由 ES 适配层。
        for child in tree.get("children", []):
            if isinstance(child, dict) and child.get("field") and child.get("value"):
                field, value = child["field"], child["value"]
                if field == "province": stmt = stmt.where(BidNotice.region == value)
                elif field == "notice_type": stmt = stmt.where(BidNotice.notice_type.contains(str(value)))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    size = min(max(int(payload.get("size", 20)), 1), 100)
    rows = db.execute(stmt.order_by(BidNotice.published_at.desc(), BidNotice.id.desc()).limit(size)).scalars().all()
    items = [{"id": row.id, "title": row.title, "notice_type": row.notice_type, "province": row.region, "purchaser": row.purchaser, "published_at": row.published_at.isoformat() if row.published_at else None, "meta": row.meta or {}} for row in rows]
    return {"total": total, "items": items, "lastSortValue": [rows[-1].published_at.isoformat() if rows and rows[-1].published_at else None, rows[-1].id] if rows else None, "engine": "mysql"}


@router.post("/search")
async def search_tenders(payload: dict[str, Any], db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    es_url = getattr(settings, "ES_URL", "")
    es_index = getattr(settings, "ES_TENDER_INDEX", "tenders")
    if es_url:
        try:
            result = await search_es(es_url, es_index, payload)
            result["engine"] = "elasticsearch"
            return {"success": True, "data": result}
        except Exception:
            pass
    return {"success": True, "data": _fallback_query(payload, db)}


@router.post("/subscriptions")
async def create_subscription(payload: dict[str, Any], db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    name = str(payload.get("name") or "未命名筛选").strip()[:128]
    snapshot = payload.get("condition_snapshot") or {}
    row = SubscriptionTask(user_id=int(user["user_id"]), name=name, condition_snapshot=snapshot, enabled=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"success": True, "data": {"id": row.id, "name": row.name, "condition_snapshot": row.condition_snapshot, "enabled": row.enabled}}


@router.get("/subscriptions")
async def list_subscriptions(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    rows = db.execute(select(SubscriptionTask).where(SubscriptionTask.user_id == int(user["user_id"]), SubscriptionTask.is_deleted == False).order_by(SubscriptionTask.id.desc())).scalars().all()
    return {"success": True, "data": [{"id": row.id, "name": row.name, "condition_snapshot": row.condition_snapshot, "enabled": row.enabled, "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None, "last_match_count": row.last_match_count} for row in rows]}
