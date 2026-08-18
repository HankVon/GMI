"""知识图谱 API — 基于大模型的开放域实体识别 + 区域关联 + 关系抽取。

能力:
  POST /knowledge/extract         单条文本 → 实体+区域+关系(不落库, 预览)
  POST /knowledge/ingest          单条文本 → 抽取并落库(Neo4j+MySQL)
  GET  /knowledge/relations/{etype}/{id}   实体全部开放关系
  GET  /knowledge/region/{name}            区域相关实体/项目
  GET  /knowledge/path            任意两实体路径(Neo4j 开放关系)
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.entity_relation import EntityRelation

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


@router.get("/relations/{entity_type}/{entity_id}")
async def entity_relations(
    entity_type: str,
    entity_id: int = 0,
    name: Optional[str] = Query(None, description="实体名(优先按名称查, 兼容未入库系统实体的知识实体)"),
    relation: Optional[str] = Query(None, description="按关系过滤, 如 COLLABORATED_WITH"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """某实体(company/person/project)的全部开放域关系(MySQL 兜底查询)。

    查询方式: ①指定 name 直接按名称查(知识图谱里未匹配到系统实体的也能查);
              ②否则用 entity_id 查系统实体名称再查。
    """
    if entity_type not in ("company", "person", "project"):
        raise HTTPException(status_code=400, detail="entity_type 需为 company/person/project")
    # 1) 优先按名称查询(知识实体, 无需系统实体id)
    if name:
        query_name = name.strip()
        if not query_name:
            raise HTTPException(status_code=400, detail="name 不能为空")
        return _query_relations(db, entity_type, query_name, relation, limit)
    # 2) 按系统实体 id 查
    from app.models.company import Company
    from app.models.person import Person
    from app.models.project import Project
    model = {"company": Company, "person": Person, "project": Project}[entity_type]
    entity = db.get(model, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="entity not found")
    query_name = entity.name or ""
    return _query_relations(db, entity_type, query_name, relation, limit,
                            entity_id=entity_id)


def _query_relations(db: Session, entity_type: str, query_name: str,
                     relation: Optional[str], limit: int,
                     entity_id: Optional[int] = None) -> dict:
    """统一关系视图: 按实体名聚合多源关系(开放域三元组/人脉边/中标人脉)。

    数据源:
      1. entity_relation — LLM 开放三元组(知识图谱)
      2. network_edge     — 人脉库聚合边(项目参与/任职/合作)
      3. bid_notice       — 中标人脉(采购人/中标供应商/代理, 近两年)
    """
    out = []

    # 1) LLM 开放三元组
    stmt = select(EntityRelation).where(
        EntityRelation.is_deleted == False,
        ((EntityRelation.source_name.contains(query_name)) |
         (EntityRelation.target_name.contains(query_name))),
    )
    if relation:
        stmt = stmt.where(EntityRelation.relation == relation)
    stmt = stmt.order_by(EntityRelation.confidence.desc(), EntityRelation.id.desc()).limit(limit)
    for r in db.execute(stmt).scalars().all():
        out.append({
            "id": r.id, "source_type": "knowledge",
            "source": {"type": r.source_type, "name": r.source_name, "id": r.source_id},
            "target": {"type": r.target_type, "name": r.target_name, "id": r.target_id},
            "relation": r.relation, "relation_zh": r.relation_zh or r.relation,
            "confidence": float(r.confidence or 0), "evidence": r.evidence or "",
            "direction": "out" if query_name in (r.source_name or "") else "in",
        })

    # 2) 人脉库边
    from app.models.business_network import NetworkEdge
    estmt = select(NetworkEdge).where(
        NetworkEdge.is_deleted == False,
        ((NetworkEdge.src_name.contains(query_name)) | (NetworkEdge.tgt_name.contains(query_name))),
    )
    if relation:
        estmt = estmt.where(NetworkEdge.rel_type == relation)
    estmt = estmt.order_by(NetworkEdge.weight.desc(), NetworkEdge.id.desc()).limit(limit)
    for e in db.execute(estmt).scalars().all():
        if query_name in (e.src_name or ""):
            direction, otype, oid, oname = "out", e.tgt_type, e.tgt_id, e.tgt_name
        else:
            direction, otype, oid, oname = "in", e.src_type, e.src_id, e.src_name
        out.append({
            "id": e.id, "source_type": "network",
            "source": {"type": e.src_type, "name": e.src_name, "id": e.src_id},
            "target": {"type": otype, "name": oname, "id": oid},
            "relation": e.rel_type, "relation_zh": e.rel_zh or e.rel_type,
            "confidence": min(1.0, float(e.weight or 0) / 3), "evidence": e.evidence or e.source or "",
            "direction": direction,
        })

    # 3) 中标人脉(近两年)
    if not relation or relation in ("IS_PURCHASER", "WON_BID", "AGENT_FOR", "中标", "采购", "代理"):
        from app.models.bid_notice import BidNotice
        bstmt = select(BidNotice).where(
            BidNotice.is_deleted == False,
            (BidNotice.purchaser.contains(query_name)) | (BidNotice.agency.contains(query_name)),
        ).order_by(BidNotice.published_at.desc()).limit(limit)
        for b in db.execute(bstmt).scalars().all():
            # 采购人方向: 该单位发标 → 中标供应商是合作方
            suppliers = []
            meta = b.meta if isinstance(b.meta, dict) else {}
            for sp in meta.get("suppliers") or []:
                sname = sp.get("supplier") or ""
                if sname and sname not in suppliers:
                    suppliers.append(sname)
            if suppliers:
                out.append({
                    "id": b.id, "source_type": "bid",
                    "source": {"type": "company", "name": b.purchaser or "", "id": b.purchaser_company_id},
                    "target": {"type": "company", "name": "；".join(suppliers[:3]), "id": None},
                    "relation": "WON_BID", "relation_zh": "中标给",
                    "confidence": 0.9, "evidence": b.title or "",
                    "direction": "out" if query_name in (b.purchaser or "") else "in",
                })
            if b.agency and query_name in (b.agency or ""):
                out.append({
                    "id": b.id, "source_type": "bid",
                    "source": {"type": "company", "name": b.agency, "id": None},
                    "target": {"type": "company", "name": b.purchaser or "", "id": b.purchaser_company_id},
                    "relation": "AGENT_FOR", "relation_zh": "代理",
                    "confidence": 0.8, "evidence": b.title or "",
                    "direction": "out" if query_name in (b.agency or "") else "in",
                })

    # 去重(按 关系+源+目标名)
    seen, deduped = set(), []
    for item in out:
        key = (item["relation"], item["source"]["name"], item["target"]["name"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return {"success": True,
            "entity": {"type": entity_type, "id": entity_id, "name": query_name},
            "items": deduped[:limit]}


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


@router.get("/path")
async def entity_path(
    a_type: str = Query(..., description="起点类型 company/person/project"),
    a_id: int = Query(...),
    b_type: str = Query(..., description="终点类型 company/person/project"),
    b_id: int = Query(...),
    max_depth: int = Query(3, ge=1, le=5),
    user: dict = Depends(get_current_user),
):
    """两实体间开放关系路径(Neo4j shortestPath)。"""
    from app.services.neo4j_sync import _get_driver
    driver = _get_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Neo4j 不可用")
    label_map = {"company": "Company", "person": "Person", "project": "Project"}
    key_map = {"company": "company_id", "person": "person_id", "project": "project_id"}
    a_l, b_l = label_map.get(a_type), label_map.get(b_type)
    a_k, b_k = key_map.get(a_type), key_map.get(b_type)
    if not a_l or not b_l:
        raise HTTPException(status_code=400, detail="type 需为 company/person/project")
    try:
        with driver.session() as s:
            rows = s.run(
                f"""
                MATCH p = shortestPath(
                  (a:{a_l} {{{a_k}: $a_id}})-[*..{max_depth}]-(b:{b_l} {{{b_k}: $b_id}}))
                WHERE NONE(n IN nodes(p) WHERE n:Region)
                RETURN [n IN nodes(p) | {{label: labels(n)[0], id: coalesce(n.company_id, n.person_id, n.project_id), name: n.name}}] AS nodes,
                       [r IN relationships(p) | {{type: type(r), zh: r.name_zh}}] AS edges
                """,
                a_id=a_id, b_id=b_id,
            ).data()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Neo4j 查询失败: {e}") from e
    return {"success": True, "paths": rows}
