"""全局搜索 API — HANDOFF §6.2.2"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, text, func
import re

from app.database import get_db
from app.models.project import Project
from app.models.person import Person
from app.models.field_meta import FieldMetadata
from app.middleware.auth import get_current_user
from app.services.dynamic_field_engine import filter_fields_by_permission

router = APIRouter(prefix="/search", tags=["全局搜索"])

SNIPPET_HALF = 50
FIXED_SCORE = 1.0


def _highlight_snippet(text: Optional[str], q: str) -> str:
    if not text:
        return "(无描述)"
    low = text.lower()
    ql = q.lower()
    idx = low.find(ql)
    if idx == -1:
        return text[:SNIPPET_HALF * 2] + ("..." if len(text) > SNIPPET_HALF * 2 else "")
    start = max(0, idx - SNIPPET_HALF)
    end = min(len(text), idx + len(q) + SNIPPET_HALF)
    snippet = text[start:end]
    snippet = re.sub(r"(?i)" + re.escape(q), lambda m: f"<em>{m.group()}</em>", snippet)
    return ("..." if start > 0 else "") + snippet + ("..." if end < len(text) else "")


@router.get("")
async def search_all(
    q: str = Query(..., min_length=1, max_length=100),
    entity_types: Optional[str] = Query(default="project,person"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """全局搜索: project FULLTEXT + person FULLTEXT + ext_attrs LIKE 兜底"""
    q = q.strip()
    if not q:
        return {"success": True, "message": "ok", "data": {"total": 0, "groups": []}}

    types = [t.strip() for t in (entity_types or "").split(",") if t.strip()]
    user_roles = user.get("roles", [])
    groups = []

    # ── project 搜索 ──
    if "project" in types:
        # 获取可搜索的动态字段（权限过滤）
        all_meta = db.execute(
            select(FieldMetadata).where(
                FieldMetadata.entity_type == "project",
                FieldMetadata.is_searchable == True,
                FieldMetadata.status == "enabled",
                FieldMetadata.is_deleted == False,
            )
        ).scalars().all()
        visible_meta = filter_fields_by_permission(all_meta, user_roles, "view")
        visible_keys = {m.field_key for m in visible_meta}

        items = []
        # FULLTEXT 主搜索
        try:
            ft_rows = db.execute(text(
                "SELECT id, code, name, description, MATCH(name,description) AGAINST(:q IN NATURAL LANGUAGE MODE) as score "
                "FROM project WHERE is_deleted=0 AND MATCH(name,description) AGAINST(:q IN NATURAL LANGUAGE MODE) > 0 "
                "ORDER BY score DESC LIMIT :limit OFFSET :offset"
            ), {"q": q, "limit": page_size, "offset": (page - 1) * page_size}).fetchall()
        except Exception:
            ft_rows = []

        seen_ids = set()
        for r in ft_rows:
            seen_ids.add(r[0])
            items.append({
                "entity_type": "project", "entity_id": r[0],
                "title": r[2] or r[1], "snippet": _highlight_snippet(r[3], q),
                "score": float(r[4]),
            })

        # ext_attrs LIKE 兜底
        if visible_keys:
            like_clauses = " OR ".join([
                f"JSON_UNQUOTE(JSON_EXTRACT(ext_attrs, '$.{k}')) LIKE :qlike"
                for k in visible_keys
            ])
            like_sql = f"""
                SELECT id, code, name, description FROM project
                WHERE is_deleted=0 AND id NOT IN :seen
                AND ({like_clauses})
                LIMIT :limit
            """
            try:
                like_rows = db.execute(text(like_sql), {
                    "qlike": f"%{q}%", "seen": tuple(seen_ids) if seen_ids else (-1,),
                    "limit": page_size - len(items),
                }).fetchall()
            except Exception:
                like_rows = []

            for r in like_rows:
                items.append({
                    "entity_type": "project", "entity_id": r[0],
                    "title": r[2] or r[1], "snippet": _highlight_snippet(r[3], q),
                    "score": FIXED_SCORE,
                })

        groups.append({"entity_type": "project", "count": len(items), "items": items})

    # ── person 搜索 ──
    if "person" in types:
        person_items = []
        try:
            p_rows = db.execute(text(
                "SELECT id, code, name, email, phone FROM person WHERE is_deleted=0 AND "
                "(name LIKE :like OR email LIKE :like) ORDER BY name LIMIT :limit OFFSET :offset"
            ), {"like": f"%{q}%", "limit": page_size, "offset": (page - 1) * page_size}).fetchall()
        except Exception:
            p_rows = []

        for r in p_rows:
            person_items.append({
                "entity_type": "person", "entity_id": r[0],
                "title": r[2] or r[1],
                "snippet": f"邮箱: {r[3] or '-'} 电话: {r[4] or '-'}" if r[3] or r[4] else _highlight_snippet(r[3], q),
                "score": FIXED_SCORE,
            })
        groups.append({"entity_type": "person", "count": len(person_items), "items": person_items})

    total = sum(g["count"] for g in groups)
    return {"success": True, "message": "ok", "data": {"total": total, "groups": groups}}
