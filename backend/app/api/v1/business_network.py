"""人脉库 API — 初始化/关系查询/专长/招标匹配。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.business_network import NetworkEdge, PersonSkill, TenderMatch

router = APIRouter(prefix="/biz-network", tags=["人脉库"])


@router.post("/init")
async def init_network(
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_company_crud")),
):
    """人脉库初始化/重建: 从项目/中标/三元组聚合人脉边 + 推导人员专长。幂等。"""
    from app.services.business_network import init_network
    result = init_network(db)
    return {"success": True, "data": result}


@router.post("/rebuild-edges")
async def rebuild_edges(
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_company_crud")),
):
    """仅重建人脉边(不清专长)。"""
    from app.services.business_network import rebuild_edges
    result = rebuild_edges(db)
    return {"success": True, "data": result}


@router.get("/edges/{entity_type}/{entity_id}")
async def entity_edges(
    entity_type: str,
    entity_id: int,
    rel: Optional[str] = Query(None, description="关系类型过滤"),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """某实体的人脉边(出边+入边聚合)。"""
    if entity_type not in ("person", "company", "project"):
        raise HTTPException(status_code=400, detail="type 需为 person/company/project")
    stmt = select(NetworkEdge).where(
        NetworkEdge.is_deleted == False,
        ((NetworkEdge.src_type == entity_type) & (NetworkEdge.src_id == entity_id)) |
        ((NetworkEdge.tgt_type == entity_type) & (NetworkEdge.tgt_id == entity_id)),
    )
    if rel:
        stmt = stmt.where(NetworkEdge.rel_type == rel)
    stmt = stmt.order_by(NetworkEdge.weight.desc(), NetworkEdge.last_seen.desc()).limit(limit)
    edges = db.execute(stmt).scalars().all()
    out = []
    for e in edges:
        if e.src_type == entity_type and e.src_id == entity_id:
            direction, otype, oid, oname = "out", e.tgt_type, e.tgt_id, e.tgt_name
        else:
            direction, otype, oid, oname = "in", e.src_type, e.src_id, e.src_name
        out.append({
            "direction": direction, "rel": e.rel_type, "rel_zh": e.rel_zh or e.rel_type,
            "weight": float(e.weight or 0), "other": {"type": otype, "id": oid, "name": oname},
            "source": e.source, "evidence": e.evidence, "last_seen": str(e.last_seen or ""),
        })
    return {"success": True, "entity": {"type": entity_type, "id": entity_id}, "items": out}


@router.get("/skills/{person_id}")
async def person_skills(
    person_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """人员专长列表。"""
    skills = db.execute(
        select(PersonSkill).where(PersonSkill.person_id == person_id, PersonSkill.is_deleted == False)
    ).scalars().all()
    return {"success": True, "person_id": person_id,
            "items": [{"skill": s.skill, "source": s.source, "confidence": float(s.confidence or 0)} for s in skills]}


@router.post("/tenders/match")
async def match_tenders(
    payload: Optional[dict] = None,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_company_crud")),
):
    """招标/意向线索 × 人脉实体 匹配(生成推荐)。"""
    from app.services.business_network import match_tenders
    clue_id = (payload or {}).get("clue_id")
    result = match_tenders(db, clue_id=clue_id)
    return {"success": True, "data": result}


@router.get("/tenders/matches")
async def tender_matches(
    status: Optional[str] = Query(None, description="状态 new/contacted/followed/ignored"),
    entity_type: Optional[str] = Query(None, description="person/company"),
    validity: Optional[str] = Query(None, description="valid/expired, 缺省全部"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """招标匹配推荐列表(支持 状态/实体类型/有效性 筛选)。

    validity: valid=未过期, expired=已过期(有效期截止自动判定, 可点「刷新有效期」重算)。
    """
    stmt = select(TenderMatch).where(TenderMatch.is_deleted == False)
    if status:
        stmt = stmt.where(TenderMatch.status == status)
    if entity_type:
        stmt = stmt.where(TenderMatch.entity_type == entity_type)
    if validity == "valid":
        stmt = stmt.where(TenderMatch.is_expired == False)
    elif validity == "expired":
        stmt = stmt.where(TenderMatch.is_expired == True)
    stmt = stmt.order_by(TenderMatch.score.desc(), TenderMatch.id.desc()).limit(limit)
    items = db.execute(stmt).scalars().all()
    out = [{
        "id": m.id, "clue_id": m.clue_id, "title": m.title,
        "entity_type": m.entity_type, "entity_id": m.entity_id, "entity_name": m.entity_name,
        "match_type": m.match_type, "match_reason": m.match_reason,
        "score": float(m.score or 0), "region": m.region, "amount": m.amount,
        "status": m.status, "created_at": str(m.created_at or ""),
        "valid_until": str(m.valid_until or ""),
        "is_expired": bool(m.is_expired),
    } for m in items]
    return {"success": True, "total": len(out), "items": out}


@router.post("/tenders/matches/refresh-validity")
async def refresh_validity(
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_company_crud")),
):
    """刷新全部招标匹配的有效期/过期标记。"""
    from app.services.business_network import refresh_match_validity
    result = refresh_match_validity(db)
    return {"success": True, "data": result}


@router.put("/tenders/matches/{match_id}/status")
async def update_match_status(
    match_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_company_crud")),
):
    """更新匹配状态(new/contacted/followed/ignored)。"""
    status = (payload.get("status") or "").strip()
    if status not in ("new", "contacted", "followed", "ignored"):
        raise HTTPException(status_code=400, detail="status 非法")
    m = db.get(TenderMatch, match_id)
    if not m or m.is_deleted:
        raise HTTPException(status_code=404, detail="match not found")
    m.status = status
    db.commit()
    return {"success": True, "message": f"已标记为「{status}」"}
