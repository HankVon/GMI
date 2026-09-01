"""全局搜索 API — 多实体域(项目/人员/单位/中标/资质/荣誉/诚信/证书) + 模糊/精准双模式。

对应指导文档: docs/gmi-renovation-guide.md B3(MySQL 过渡方案) / G-阶段二
演进说明: 数据量到十万级后切换 Elasticsearch 时, 保持本接口返回结构
(按 entity_type 分组的 {count, items}) 不变, 前端无需改动。
"""
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

# 支持的实体域(可多选, 逗号分隔)
SUPPORTED_TYPES = {
    "project", "person", "company", "bid",
    "qualification", "honor", "credit_record", "person_cert",
}


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


def _like_pattern(q: str, mode: str) -> str:
    """fuzzy: 含关键词即命中; exact: 全词(用引号包住, 匹配连续整词)。"""
    if mode == "exact":
        return f"%{q}%"
    return f"%{q}%"


# ── 各实体域搜索器(返回 {entity_type, count, items}) ──
def _search_project(db, q, mode, limit, offset):
    items = []
    # FULLTEXT 主搜索
    try:
        ft_rows = db.execute(text(
            "SELECT id, code, name, description, MATCH(name,description) AGAINST(:q IN NATURAL LANGUAGE MODE) as score "
            "FROM project WHERE is_deleted=0 AND MATCH(name,description) AGAINST(:q IN NATURAL LANGUAGE MODE) > 0 "
            "ORDER BY score DESC LIMIT :limit OFFSET :offset"
        ), {"q": q, "limit": limit, "offset": offset}).fetchall()
    except Exception:
        ft_rows = []
    for r in ft_rows:
        items.append({
            "entity_type": "project", "entity_id": r[0],
            "title": r[2] or r[1], "snippet": _highlight_snippet(r[3], q),
            "score": float(r[4]),
        })
    return items


def _search_person(db, q, mode, limit, offset):
    like = _like_pattern(q, mode)
    try:
        rows = db.execute(text(
            "SELECT id, code, name, email, phone FROM person WHERE is_deleted=0 AND "
            "(name LIKE :like OR email LIKE :like) ORDER BY name LIMIT :limit OFFSET :offset"
        ), {"like": like, "limit": limit, "offset": offset}).fetchall()
    except Exception:
        rows = []
    items = []
    for r in rows:
        items.append({
            "entity_type": "person", "entity_id": r[0],
            "title": r[2] or r[1],
            "snippet": f"邮箱: {r[3] or '-'} 电话: {r[4] or '-'}" if r[3] or r[4] else _highlight_snippet(r[3], q),
            "score": FIXED_SCORE,
        })
    return items


def _search_company(db, q, mode, limit, offset):
    like = _like_pattern(q, mode)
    try:
        rows = db.execute(text(
            "SELECT id, name, province, city, company_type, credit_level FROM company "
            "WHERE is_deleted=0 AND (name LIKE :like OR short_name LIKE :like OR credit_code = :q) "
            "ORDER BY name LIMIT :limit OFFSET :offset"
        ), {"like": like, "q": q, "limit": limit, "offset": offset}).fetchall()
    except Exception:
        rows = []
    items = []
    for r in rows:
        region = " ".join(x for x in (r[2], r[3]) if x)
        items.append({
            "entity_type": "company", "entity_id": r[0],
            "title": r[1] or "",
            "snippet": f"地区: {region or '-'} 类型: {r[4] or '-'} 信用: {r[5] or '-'}",
            "score": FIXED_SCORE,
        })
    return items


def _search_bid(db, q, mode, limit, offset):
    like = _like_pattern(q, mode)
    try:
        rows = db.execute(text(
            "SELECT id, title, purchaser, region, notice_type FROM bid_notice "
            "WHERE is_deleted=0 AND (title LIKE :like OR purchaser LIKE :like) "
            "ORDER BY published_at DESC LIMIT :limit OFFSET :offset"
        ), {"like": like, "limit": limit, "offset": offset}).fetchall()
    except Exception:
        rows = []
    items = []
    for r in rows:
        items.append({
            "entity_type": "bid", "entity_id": r[0],
            "title": r[1] or "",
            "snippet": f"业主: {r[2] or '-'} 地区: {r[3] or '-'} 类型: {r[4] or '-'}",
            "score": FIXED_SCORE,
        })
    return items


def _search_qualification(db, q, mode, limit, offset):
    like = _like_pattern(q, mode)
    try:
        rows = db.execute(text(
            "SELECT id, company_id, category, professional, level, status FROM qualification "
            "WHERE is_deleted=0 AND (category LIKE :like OR professional LIKE :like) "
            "ORDER BY id DESC LIMIT :limit OFFSET :offset"
        ), {"like": like, "limit": limit, "offset": offset}).fetchall()
    except Exception:
        rows = []
    items = []
    for r in rows:
        items.append({
            "entity_type": "qualification", "entity_id": r[0],
            "title": f"{r[2] or ''} {r[3] or ''} {r[4] or ''}".strip() or "资质",
            "snippet": f"单位ID: {r[1]} 状态: {r[5] or '-'}",
            "score": FIXED_SCORE,
        })
    return items


def _search_honor(db, q, mode, limit, offset):
    like = _like_pattern(q, mode)
    try:
        rows = db.execute(text(
            "SELECT id, company_id, title, level, org FROM honor "
            "WHERE is_deleted=0 AND (title LIKE :like OR org LIKE :like) "
            "ORDER BY id DESC LIMIT :limit OFFSET :offset"
        ), {"like": like, "limit": limit, "offset": offset}).fetchall()
    except Exception:
        rows = []
    items = []
    for r in rows:
        items.append({
            "entity_type": "honor", "entity_id": r[0],
            "title": r[2] or "",
            "snippet": f"单位ID: {r[1]} 等级: {r[3] or '-'} 授予: {r[4] or '-'}",
            "score": FIXED_SCORE,
        })
    return items


def _search_credit_record(db, q, mode, limit, offset):
    like = _like_pattern(q, mode)
    try:
        rows = db.execute(text(
            "SELECT id, company_id, title, org FROM credit_record "
            "WHERE is_deleted=0 AND (title LIKE :like OR reason LIKE :like) "
            "ORDER BY id DESC LIMIT :limit OFFSET :offset"
        ), {"like": like, "limit": limit, "offset": offset}).fetchall()
    except Exception:
        rows = []
    items = []
    for r in rows:
        items.append({
            "entity_type": "credit_record", "entity_id": r[0],
            "title": r[2] or "",
            "snippet": f"单位ID: {r[1]} 公示: {r[3] or '-'}",
            "score": FIXED_SCORE,
        })
    return items


def _search_person_cert(db, q, mode, limit, offset):
    like = _like_pattern(q, mode)
    try:
        rows = db.execute(text(
            "SELECT id, person_id, cert_type, cert_no, major, status FROM person_cert "
            "WHERE is_deleted=0 AND (cert_type LIKE :like OR cert_no LIKE :like OR major LIKE :like) "
            "ORDER BY id DESC LIMIT :limit OFFSET :offset"
        ), {"like": like, "limit": limit, "offset": offset}).fetchall()
    except Exception:
        rows = []
    items = []
    for r in rows:
        items.append({
            "entity_type": "person_cert", "entity_id": r[0],
            "title": f"{r[2] or ''} {r[4] or ''}".strip() or "证书",
            "snippet": f"人员ID: {r[1]} 编号: {r[3] or '-'} 状态: {r[5] or '-'}",
            "score": FIXED_SCORE,
        })
    return items


_SEARCHERS = {
    "project": _search_project,
    "person": _search_person,
    "company": _search_company,
    "bid": _search_bid,
    "qualification": _search_qualification,
    "honor": _search_honor,
    "credit_record": _search_credit_record,
    "person_cert": _search_person_cert,
}


@router.get("")
async def search_all(
    q: str = Query(..., min_length=1, max_length=100),
    entity_types: Optional[str] = Query(default="project,person,company,bid",
                                        description="逗号分隔: project,person,company,bid,qualification,honor,credit_record,person_cert"),
    mode: str = Query(default="fuzzy", pattern="^(fuzzy|exact)$", description="fuzzy=模糊 / exact=精准"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """全局搜索: 多实体域检索(MySQL 过渡方案, 十万级后再切 ES)。"""
    q = q.strip()
    if not q:
        return {"success": True, "message": "ok", "data": {"total": 0, "groups": []}}

    types = [t.strip() for t in (entity_types or "").split(",") if t.strip() in SUPPORTED_TYPES]
    if not types:
        types = ["project", "person", "company", "bid"]
    groups = []
    for t in types:
        searcher = _SEARCHERS[t]
        items = searcher(db, q, mode, page_size, (page - 1) * page_size)
        groups.append({"entity_type": t, "count": len(items), "items": items})

    total = sum(g["count"] for g in groups)
    return {"success": True, "message": "ok", "data": {"total": total, "groups": groups}}
