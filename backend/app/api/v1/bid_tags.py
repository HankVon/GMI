"""标讯标签管理 API — 标签字典 CRUD + 自动打标 + 单条打标。"""
import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.bid_notice import BidNotice
from app.models.bid_tag import BidTagDef, BidNoticeTag
from app.services.audit_service import log_action

router = APIRouter(prefix="/admin/bid-tags", tags=["标讯标签"])


def _tag_dict(t: BidTagDef) -> dict:
    return {
        "id": t.id,
        "label": t.label,
        "kind": t.kind,
        "rule_keyword": t.rule_keyword,
        "sort_order": t.sort_order,
        "enabled": t.enabled,
        "created_at": t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "",
    }


@router.get("/defs")
async def list_tags(
    keyword: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_view")),
):
    """标签字典列表。"""
    stmt = select(BidTagDef).where(BidTagDef.is_deleted == False)  # noqa: E712
    if keyword:
        stmt = stmt.where(BidTagDef.label.contains(keyword))
    if enabled is not None:
        stmt = stmt.where(BidTagDef.enabled == enabled)
    rows = db.execute(stmt.order_by(BidTagDef.sort_order, BidTagDef.id.desc())).scalars().all()
    return {"success": True, "items": [_tag_dict(r) for r in rows]}


@router.post("/defs")
async def create_tag(
    payload: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_tag_manage")),
):
    """新建标签。"""
    label = str(payload.get("label") or "").strip()
    if not label:
        raise HTTPException(status_code=422, detail="标签文本不能为空")
    exists = db.execute(
        select(BidTagDef).where(BidTagDef.label == label, BidTagDef.is_deleted == False)  # noqa: E712
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail=f"标签「{label}」已存在")
    t = BidTagDef(
        label=label,
        kind=payload.get("kind") or "category",
        rule_keyword=payload.get("rule_keyword") or None,
        sort_order=payload.get("sort_order") or 0,
        enabled=payload.get("enabled", True),
    )
    db.add(t)
    db.flush()
    log_action(db, user.get("user_id"), user.get("username") or user.get("display_name"),
               "tag_create", "bid_tag", t.id, label)
    db.commit()
    db.refresh(t)
    return {"success": True, "data": _tag_dict(t)}


@router.put("/defs/{tag_id}")
async def update_tag(
    tag_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_tag_manage")),
):
    """编辑标签。"""
    t = db.get(BidTagDef, tag_id)
    if not t or t.is_deleted:
        raise HTTPException(status_code=404, detail="标签不存在")
    if payload.get("label") is not None:
        t.label = str(payload["label"]).strip() or t.label
    if payload.get("kind") is not None:
        t.kind = payload["kind"]
    if payload.get("rule_keyword") is not None:
        t.rule_keyword = payload["rule_keyword"]
    if payload.get("sort_order") is not None:
        t.sort_order = payload["sort_order"]
    if payload.get("enabled") is not None:
        t.enabled = payload["enabled"]
    db.commit()
    return {"success": True, "data": _tag_dict(t)}


@router.delete("/defs/{tag_id}")
async def delete_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_tag_manage")),
):
    """删除标签(同时解除关联)。"""
    t = db.get(BidTagDef, tag_id)
    if not t or t.is_deleted:
        raise HTTPException(status_code=404, detail="标签不存在")
    t.is_deleted = True
    db.execute(delete(BidNoticeTag).where(BidNoticeTag.tag_id == tag_id))
    log_action(db, user.get("user_id"), user.get("username") or user.get("display_name"),
               "tag_delete", "bid_tag", tag_id, t.label)
    db.commit()
    return {"success": True}


# ============================================================
# 打标(单条打标走 /admin/bids/{id}/tags, 见 bid_admin.py)
# ============================================================
@router.post("/auto-apply")
async def auto_apply_tags(
    payload: Optional[dict] = None,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_tag_manage")),
):
    """按规则关键字自动打标: 标题命中 rule_keyword 的标签自动关联。"""
    rules = db.execute(
        select(BidTagDef).where(
            BidTagDef.is_deleted == False,  # noqa: E712
            BidTagDef.enabled == True,  # noqa: E712
            BidTagDef.rule_keyword.isnot(None),
            BidTagDef.rule_keyword != "",
        )
    ).scalars().all()
    bid_ids = payload.get("bid_ids") if payload else None
    stmt = select(BidNotice).where(BidNotice.is_deleted == False)  # noqa: E712
    if bid_ids:
        stmt = stmt.where(BidNotice.id.in_([int(x) for x in bid_ids]))
    bids = db.execute(stmt.limit(500)).scalars().all()

    applied = 0
    for bn in bids:
        title = bn.title or ""
        for rule in rules:
            for kw in [k.strip() for k in (rule.rule_keyword or "").split(",") if k.strip()]:
                if kw in title:
                    exists = db.execute(
                        select(BidNoticeTag.id).where(
                            BidNoticeTag.bid_id == bn.id, BidNoticeTag.tag_id == rule.id
                        )
                    ).scalar_one_or_none()
                    if not exists:
                        db.add(BidNoticeTag(bid_id=bn.id, tag_id=rule.id, created_by=user.get("user_id")))
                        applied += 1
    db.flush()
    log_action(db, user.get("user_id"), user.get("username") or user.get("display_name"),
               "bid_tag_auto", "bid_tag", 0, f"auto apply {applied} links")
    db.commit()
    return {"success": True, "data": {"applied": applied, "scanned": len(bids)}}
