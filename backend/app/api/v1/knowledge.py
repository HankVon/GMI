"""知识图谱 API — 基于大模型的开放域实体识别 + 区域关联 + 关系抽取。

能力:
  POST /knowledge/extract         单条文本 → 实体+区域+关系(不落库, 预览)
  POST /knowledge/ingest          单条文本 → 抽取并落库(Neo4j+MySQL)
  GET  /knowledge/region/{name}   区域相关实体/项目

注: 原 /knowledge/relations、/knowledge/path 两个读端点因前端零调用、且已被
     /network/* 人脉/图谱端点取代, 作为孤儿接口下线(见 P2-1 清理)。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission

router = APIRouter(prefix="/knowledge", tags=["知识图谱"])


@router.post("/extract")
async def extract_knowledge_api(
    payload: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """单条文本 → 实体识别 + 区域关联 + 开放域关系(预览, 不落库)。"""
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 不能为空")
    from app.services.knowledge_extractor import extract_knowledge
    result = extract_knowledge(text)
    return {"success": True, "data": result}


@router.post("/ingest")
async def ingest_knowledge_api(
    payload: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_project_crud")),
):
    """单条文本 → 抽取并落库(Neo4j 区域/开放关系 + MySQL 三元组)。"""
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 不能为空")
    source_text_id = payload.get("source_text_id")
    from app.services.knowledge_ingest import ingest_knowledge
    stats = ingest_knowledge(db, text, source_text_id=source_text_id)
    return {"success": True, "data": stats}


@router.get("/region/{name}")
async def region_entities(
    name: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """区域相关实体/项目(按实体区域属性 + entity_relation 区域关联)。"""
    from app.models.company import Company
    from app.models.project import Project
    from app.services.china_regions import resolve_region

    rg = resolve_region("", name, "")
    core = rg.get("province") or rg.get("city") or name
    out = {"region": name, "resolved": rg, "companies": [], "projects": []}
    # 公司: province/city 含核心词
    comps = db.execute(
        select(Company).where(
            Company.is_deleted == False,
            ((Company.province.contains(core)) | (Company.city.contains(core))),
        ).limit(limit)
    ).scalars().all()
    out["companies"] = [{"id": c.id, "name": c.name, "province": c.province, "city": c.city} for c in comps]
    # 项目: ext_attrs 含区域(MySQL JSON 查询)
    projects = db.execute(
        select(Project).where(Project.is_deleted == False).limit(200)
    ).scalars().all()
    matched = []
    for p in projects:
        ext = p.ext_attrs or {}
        pv = str(ext.get("province") or "")
        cv = str(ext.get("city") or "")
        if core and (core in pv or core in cv or core in (p.name or "")):
            matched.append({"id": p.id, "name": p.name, "province": pv, "city": cv})
        if len(matched) >= limit:
            break
    out["projects"] = matched
    return {"success": True, "data": out}
