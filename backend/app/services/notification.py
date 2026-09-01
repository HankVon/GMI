"""站内通知服务 — 创建通知(支持单用户/多用户/管理员角色)。

触发点:
  - 线索过期(clue_expire): scheduler 每日清理标记过期线索时通知相关用户
  - 项目进度变更(progress): project_progress 创建时通知项目负责人/成员
  - 新中标(bid_new): bid_notice 创建时通知关注用户(简化: admin 角色)
"""
from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.rbac import SysUser, SysUserRole, SysRole

logger = logging.getLogger("notification")

# 通知类型
T_CLUE_EXPIRE = "clue_expire"
T_PROGRESS = "progress"
T_BID_NEW = "bid_new"
T_SYSTEM = "system"


def create_notifications(db: Session, user_ids: Iterable[int], type_: str,
                         title: str, content: str | None = None,
                         related_type: str | None = None,
                         related_id: int | None = None) -> int:
    """为指定用户批量创建通知(失败不阻断主流程)。返回创建条数。"""
    ids = [int(uid) for uid in user_ids if uid]
    if not ids:
        return 0
    try:
        for uid in ids:
            db.add(Notification(user_id=uid, type=type_, title=title,
                                content=content, related_type=related_type,
                                related_id=related_id))
        db.commit()
        return len(ids)
    except Exception as e:  # noqa: BLE001 - 通知失败不影响主流程
        logger.warning("[notify] create_notifications failed: %s", e)
        db.rollback()
        return 0


def notify_admin_users(db: Session, type_: str, title: str,
                       content: str | None = None,
                       related_type: str | None = None,
                       related_id: int | None = None) -> int:
    """通知所有 admin 角色用户。"""
    user_ids = db.execute(
        select(SysUserRole.user_id).join(SysRole, SysRole.id == SysUserRole.role_id)
        .where(SysRole.code == "admin", SysRole.is_deleted == False)  # noqa: E712
    ).scalars().all()
    return create_notifications(db, user_ids, type_, title, content,
                                related_type, related_id)


def notify_user(db: Session, user_id: int, type_: str, title: str,
                content: str | None = None, related_type: str | None = None,
                related_id: int | None = None) -> int:
    """通知单个用户。"""
    return create_notifications(db, [user_id], type_, title, content,
                                related_type, related_id)
