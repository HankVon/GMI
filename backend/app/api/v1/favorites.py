"""收藏与标签 API — A4 / 阶段三。

端点:
- POST /favorites/toggle      收藏/取消收藏(幂等)
- GET  /favorites/state       单实体收藏状态 + 标签(详情页按钮用)
- GET  /favorites             我的收藏列表(按类型过滤, 回填名称 + 新标记)
- GET  /favorites/summary     我的收藏聚合(按类型分组计数 + 各类型最新几条)
- POST /favorites/tags        增加个人标签
- DELETE /favorites/tags      删除个人标签

竞争跟踪「新」标记: 实体 updated_at 晚于收藏时间 favorited_at 即视为有更新。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.favorite import Favorite, Tag
from app.models.company import Company
from app.models.project import Project
from app.models.person import Person
from app.models.opportunity import Opportunity

router = APIRouter(prefix="/favorites", tags=["收藏与标签"])

_VALID_TYPES = {"company", "project", "person", "opportunity"}


class FavToggle(BaseModel):
    entity_type: str
    entity_id: int


class TagPayload(BaseModel):
    entity_type: str
    entity_id: int
    tag: str


def _uid(user: dict) -> int:
    return int(user["user_id"])


def _entity_row(db: Session, entity_type: str, entity_id: int):
    if entity_type == "company":
        return db.get(Company, entity_id)
    if entity_type == "project":
        return db.get(Project, entity_id)
    if entity_type == "person":
        return db.get(Person, entity_id)
    if entity_type == "opportunity":
        return db.get(Opportunity, entity_id)
    return None


def _entity_name(db: Session, entity_type: str, entity_id: int) -> Optional[str]:
    row = _entity_row(db, entity_type, entity_id)
    if not row:
        return None
    # 商机表主键名是 project_name(其余实体为 name), 两者兼容
    return getattr(row, "name", None) or getattr(row, "project_name", None)


def _check_type(entity_type: str):
    if entity_type not in _VALID_TYPES:
        raise HTTPException(status_code=422, detail="entity_type 必须是 company/project/person")


@router.post("/toggle")
async def toggle_favorite(
    payload: FavToggle,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _check_type(payload.entity_type)
    uid = _uid(user)
    row = db.execute(
        select(Favorite).where(
            Favorite.user_id == uid,
            Favorite.entity_type == payload.entity_type,
            Favorite.entity_id == payload.entity_id,
        )
    ).scalar_one_or_none()
    if row:
        db.delete(row)
        active = False
    else:
        db.add(
            Favorite(
                user_id=uid,
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
            )
        )
        active = True
    db.commit()
    return {"success": True, "data": {"active": active}}


@router.get("/state")
async def fav_state(
    entity_type: str,
    entity_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _check_type(entity_type)
    uid = _uid(user)
    fav = db.execute(
        select(Favorite).where(
            Favorite.user_id == uid,
            Favorite.entity_type == entity_type,
            Favorite.entity_id == entity_id,
        )
    ).scalar_one_or_none()
    tags = db.execute(
        select(Tag.tag).where(
            Tag.user_id == uid,
            Tag.entity_type == entity_type,
            Tag.entity_id == entity_id,
        )
    ).scalars().all()
    return {
        "success": True,
        "data": {
            "active": bool(fav),
            "tags": list(tags),
            "favorited_at": fav.created_at.isoformat() if fav and fav.created_at else None,
        },
    }


@router.get("")
async def list_favorites(
    entity_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if entity_type:
        _check_type(entity_type)
    uid = _uid(user)
    base = select(Favorite).where(Favorite.user_id == uid)
    if entity_type:
        base = base.where(Favorite.entity_type == entity_type)
    count_q = select(func.count()).select_from(Favorite).where(Favorite.user_id == uid)
    if entity_type:
        count_q = count_q.where(Favorite.entity_type == entity_type)
    total = db.execute(count_q).scalar() or 0
    rows = db.execute(
        base.order_by(Favorite.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    items = []
    for r in rows:
        name = _entity_name(db, r.entity_type, r.entity_id)
        row = _entity_row(db, r.entity_type, r.entity_id)
        ent_updated = row.updated_at.isoformat() if row and row.updated_at else None
        fav_at = r.created_at.isoformat() if r.created_at else None
        item_tags = db.execute(
            select(Tag.tag).where(
                Tag.user_id == uid,
                Tag.entity_type == r.entity_type,
                Tag.entity_id == r.entity_id,
            )
        ).scalars().all()
        items.append({
            "id": r.id,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "name": name,
            "tags": list(item_tags),
            "favorited_at": fav_at,
            "entity_updated_at": ent_updated,
            "is_new": bool(ent_updated and fav_at and ent_updated > fav_at),
        })
    return {
        "success": True,
        "data": {"total": total, "page": page, "page_size": page_size, "items": items},
    }


@router.get("/summary")
async def fav_summary(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    uid = _uid(user)
    groups: dict = {}
    for et in _VALID_TYPES:
        cnt = db.execute(
            select(func.count()).select_from(Favorite).where(
                Favorite.user_id == uid, Favorite.entity_type == et
            )
        ).scalar() or 0
        recents = db.execute(
            select(Favorite)
            .where(Favorite.user_id == uid, Favorite.entity_type == et)
            .order_by(Favorite.created_at.desc())
            .limit(5)
        ).scalars().all()
        items = [
            {
                "entity_id": r.entity_id,
                "name": _entity_name(db, et, r.entity_id),
                "favorited_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recents
        ]
        groups[et] = {"count": cnt, "items": items}
    return {"success": True, "data": groups}


@router.post("/tags")
async def add_tag(
    payload: TagPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _check_type(payload.entity_type)
    tag = (payload.tag or "").strip()
    if not tag:
        raise HTTPException(status_code=422, detail="tag 不能为空")
    uid = _uid(user)
    exists = db.execute(
        select(Tag).where(
            Tag.user_id == uid,
            Tag.entity_type == payload.entity_type,
            Tag.entity_id == payload.entity_id,
            Tag.tag == tag,
        )
    ).scalar_one_or_none()
    if not exists:
        db.add(
            Tag(
                user_id=uid,
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
                tag=tag,
            )
        )
        db.commit()
    tags = db.execute(
        select(Tag.tag).where(
            Tag.user_id == uid,
            Tag.entity_type == payload.entity_type,
            Tag.entity_id == payload.entity_id,
        )
    ).scalars().all()
    return {"success": True, "data": {"tags": list(tags)}}


@router.delete("/tags")
async def remove_tag(
    payload: TagPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    uid = _uid(user)
    db.execute(
        Tag.__table__.delete().where(
            Tag.user_id == uid,
            Tag.entity_type == payload.entity_type,
            Tag.entity_id == payload.entity_id,
            Tag.tag == (payload.tag or "").strip(),
        )
    )
    db.commit()
    tags = db.execute(
        select(Tag.tag).where(
            Tag.user_id == uid,
            Tag.entity_type == payload.entity_type,
            Tag.entity_id == payload.entity_id,
        )
    ).scalars().all()
    return {"success": True, "data": {"tags": list(tags)}}
