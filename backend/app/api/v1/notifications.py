"""站内通知 API — 列表/未读数/标记已读"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.notification import Notification

router = APIRouter(prefix="/notifications", tags=["站内通知"])


@router.get("")
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = False,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """当前用户通知列表(分页, 新→旧)。"""
    uid = int(user["user_id"])
    conds = [Notification.user_id == uid, Notification.is_deleted == False]  # noqa: E712
    if unread_only:
        conds.append(Notification.is_read == False)  # noqa: E712
    total = db.execute(select(func.count(Notification.id)).where(*conds)).scalar() or 0
    rows = db.execute(
        select(Notification).where(*conds)
        .order_by(Notification.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return {
        "success": True,
        "data": {
            "total": total,
            "items": [{
                "id": n.id, "type": n.type, "title": n.title, "content": n.content,
                "related_type": n.related_type, "related_id": n.related_id,
                "is_read": n.is_read, "status": n.status or "pending",
                "created_at": n.created_at.isoformat() if n.created_at else None,
            } for n in rows],
        },
    }


@router.patch("/{notification_id}/status")
async def update_notification_status(notification_id: int, body: dict, db: Session = Depends(get_db), user: dict = Depends(require_permission("api_notification"))):
    """更新通知/咨询反馈处理状态。"""
    status_value = body.get("status", "").lower()
    if status_value not in {"pending", "processing", "resolved", "closed"}:
        raise HTTPException(status_code=422, detail="无效处理状态")
    row = db.execute(select(Notification).where(Notification.id == notification_id, Notification.is_deleted == False)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="通知不存在")
    row.status = status_value
    db.commit()
    return {"success": True, "status": status_value}


@router.get("/contact")
async def list_contact_requests(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), user: dict = Depends(require_permission("api_notification"))):
    """反馈处理队列，仅对拥有通知权限的登录用户开放。"""
    conds = [Notification.user_id == 0, Notification.type == "contact", Notification.is_deleted == False]
    total = db.execute(select(func.count(Notification.id)).where(*conds)).scalar() or 0
    rows = db.execute(select(Notification).where(*conds).order_by(Notification.id.desc()).offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return {"success": True, "data": {"total": total, "items": [{"id": n.id, "title": n.title, "content": n.content, "status": n.status or "pending", "created_at": n.created_at.isoformat() if n.created_at else None} for n in rows]}}


@router.get("/unread-count")
async def unread_count(db: Session = Depends(get_db),
                       user: dict = Depends(get_current_user)):
    """未读通知数(前端铃铛角标)。"""
    uid = int(user["user_id"])
    n = db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == uid,
            Notification.is_read == False,  # noqa: E712
            Notification.is_deleted == False,  # noqa: E712
        )
    ).scalar() or 0
    return {"success": True, "data": {"unread": n}}


class MarkReadBody(BaseModel):
    ids: list[int] = Field(default_factory=list, description="要标记的通知ID; 空则忽略")
    all: bool = Field(default=False, description="标记全部为已读(优先于 ids)")


@router.post("/read")
async def mark_read(body: MarkReadBody, db: Session = Depends(get_db),
                    user: dict = Depends(get_current_user)):
    """标记已读: all=true 标记全部; 否则按 ids 标记。"""
    uid = int(user["user_id"])
    if body.all:
        db.execute(
            Notification.__table__.update()
            .where(Notification.user_id == uid, Notification.is_read == False)  # noqa: E712
            .values(is_read=True)
        )
    elif body.ids:
        db.execute(
            Notification.__table__.update()
            .where(Notification.user_id == uid, Notification.id.in_(body.ids))
            .values(is_read=True)
        )
    db.commit()
    return {"success": True, "message": "ok"}
