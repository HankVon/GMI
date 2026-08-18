"""知识落库服务 — 把 LLM 抽取的实体/区域/关系写入 Neo4j + MySQL。

流程:
  1. 实体名 → 系统实体匹配(company/person/project 表, 精确/包含), 拿到实体id
  2. 区域节点 + BELONGS_TO 层级 + 实体 IN_REGION 挂载
  3. 开放关系写 Neo4j(sync_open_relation) + MySQL(entity_relation 表, 幂等)
Neo4j 不可用时 MySQL 兜底(降级查询)。
"""
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.person import Person
from app.models.project import Project
from app.models.entity_relation import EntityRelation
from app.services import neo4j_sync
from app.services.china_regions import resolve_region

logger = logging.getLogger("knowledge_ingest")


def _match_system_entity(db: Session, etype: str, name: str) -> Optional[int]:
    """实体名 → 系统实体id(company/person/project), 未命中返回 None。"""
    if not name:
        return None
    name = name.strip()
    if etype == "company":
        stmt = select(Company).where(Company.is_deleted == False).order_by(Company.id)
    elif etype == "person":
        stmt = select(Person).where(Person.is_deleted == False).order_by(Person.id)
    elif etype == "project":
        stmt = select(Project).where(Project.is_deleted == False).order_by(Project.id)
    else:
        return None
    rows = db.execute(stmt).scalars().all()
    # 精确 → 包含(较长的优先)
    for r in rows:
        if (r.name or "") == name:
            return r.id
    for r in rows:
        if name and (name in (r.name or "") or (r.name or "") in name):
            return r.id
    return None


def ingest_knowledge(db: Session, text: str, source_text_id: Optional[int] = None) -> dict:
    """抽取 + 落库一条文本的知识(实体/区域/开放关系)。返回统计。"""
    from app.services.knowledge_extractor import extract_knowledge

    result = extract_knowledge(text)
    entities = result.get("entities") or []
    relations = result.get("relations") or []
    regions = result.get("regions") or []

    stats = {"entities": len(entities), "relations": len(relations),
             "regions": len(regions), "matched_entities": 0, "stored_relations": 0,
             "neo4j_ok": True}

    # 1) 区域节点 + 层级(幂等)
    for rg in regions:
        try:
            neo4j_sync.sync_region_hierarchy(rg.get("province", ""), rg.get("city", ""), rg.get("county", ""))
        except Exception as e:  # noqa: BLE001
            logger.warning("区域同步失败: %s", e)

    # 2) 实体挂区域 + 记 id
    entity_ids = {}
    for e in entities:
        etype = e["type"]
        if etype not in ("company", "person", "project"):
            continue
        eid = _match_system_entity(db, etype, e["name"])
        if eid:
            stats["matched_entities"] += 1
            entity_ids[(etype, e["name"])] = eid
        rg = resolve_region(e.get("province", ""), e.get("city", ""), e.get("county", ""))
        if rg.get("matched"):
            try:
                neo4j_sync.sync_entity_region(etype, eid or -1, e["name"], rg)
            except Exception as ex:  # noqa: BLE001
                logger.warning("实体区域挂载失败: %s", ex)

    # 3) 开放关系落库(Neo4j + MySQL 双写)
    for rel in relations:
        s_type = _etype_from_entity(entities, rel["source"])
        t_type = _etype_from_entity(entities, rel["target"])
        if not s_type or not t_type:
            continue
        s_id = entity_ids.get((s_type, rel["source"]))
        t_id = entity_ids.get((t_type, rel["target"]))
        # MySQL 兜底(幂等: 同关系同证据不重复)
        exists = db.execute(
            select(EntityRelation).where(
                EntityRelation.source_name == rel["source"],
                EntityRelation.target_name == rel["target"],
                EntityRelation.relation == rel["relation"],
                EntityRelation.is_deleted == False,
            ).limit(1)
        ).scalar_one_or_none()
        if not exists:
            db.add(EntityRelation(
                source_type=s_type, source_name=rel["source"], source_id=s_id,
                target_type=t_type, target_name=rel["target"], target_id=t_id,
                relation=rel["relation"], relation_zh=rel.get("relation_zh", rel["relation"]),
                confidence=rel.get("confidence", 0.8), evidence=rel.get("evidence", ""),
                source_text_id=source_text_id,
            ))
            db.flush()
        stats["stored_relations"] += 1
        # Neo4j 开放关系
        if s_id and t_id:
            try:
                neo4j_sync.sync_open_relation(
                    s_type, s_id, rel["source"], t_type, t_id, rel["target"],
                    rel["relation"], rel.get("relation_zh", rel["relation"]),
                    confidence=rel.get("confidence", 0.8), evidence=rel.get("evidence", ""),
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("Neo4j 开放关系同步失败: %s", e)
                stats["neo4j_ok"] = False

    db.commit()
    return stats


def _etype_from_entity(entities: list, name: str) -> Optional[str]:
    """实体名 → 类型(company/person/project)。"""
    for e in entities:
        if e["name"] == name and e["type"] in ("company", "person", "project"):
            return e["type"]
    return None
