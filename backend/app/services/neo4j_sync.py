"""Neo4j 知识图谱实时同步服务。

设计:
  - MySQL 为主数据源, Neo4j 为图谱投影; 本模块在所有写操作 commit 之后被调用。
  - Neo4j 不可用时**静默降级**(只记录 warning, 绝不阻断 MySQL 主流程)。
  - 同步保持幂等: 一律使用 MERGE + 唯一键。

图模型:
  (Person {person_id})-[:WORKS_AT]->(Company {company_id})
  (Person {person_id})-[:PARTICIPATES_IN {role}]->(Project {project_id})
  (Company {company_id})-[:PARTICIPATES_IN {role}]->(Project {project_id})
  (Person {person_id})-[:COLLABORATED_WITH {via_project_id}]->(Person {person_id})  同项目合作过(双向)

用法:
  from app.services.neo4j_sync import sync_person, sync_project, sync_project_members, ...
"""
from __future__ import annotations

import logging
from typing import Any, Protocol, cast

from app.config import settings

logger = logging.getLogger("neo4j_sync")


class ProjectLike(Protocol):
    """同步所需的 Project 最小结构(SQLAlchemy 模型或 dict 兼容对象均可)。"""

    id: int
    name: str
    code: str | None
    status: str | None
    ext_attrs: dict | None

# 关系中文名: 同步时写入关系属性 name_zh, 图谱自解释
RELATION_NAMES_ZH = {
    "WORKS_AT": "任职于",
    "PARTICIPATES_IN": "参与",
    "COLLABORATED_WITH": "合作过",
    "COLLEAGUE": "同事",
}

_Driver = None
# Neo4j 熔断: 连接失败后 _CIRCUIT_SECONDS 内不再重试, 避免每个写接口重试风暴导致响应卡顿
_CIRCUIT_SECONDS = 60.0
_last_failure_ts = 0.0


def _get_driver():
    """惰性创建 Neo4j 驱动, 连接失败返回 None(降级)。

    失败后进入熔断窗口(_CIRCUIT_SECONDS), 窗口内直接返回 None, 不再反复 verify_connectivity,
    防止项目保存等高频写接口在 Neo4j 不可达时被拖慢(单次最长可达 connection_timeout)。
    """
    global _Driver, _last_failure_ts
    if _Driver is not None:
        return _Driver
    import time

    now = time.monotonic()
    if now - _last_failure_ts < _CIRCUIT_SECONDS:
        return None
    uri = settings.NEO4J_URI
    if not uri:
        return None
    try:
        from neo4j import GraphDatabase

        _Driver = GraphDatabase.driver(
            uri,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            connection_timeout=5,
            max_connection_pool_size=10,
        )
        # 验证连通性, 失败抛异常 -> 置 None 降级
        _Driver.verify_connectivity()
    except Exception as e:  # noqa: BLE001
        logger.warning("Neo4j 不可用, 图谱同步降级跳过: %s", e)
        _Driver = None
        _last_failure_ts = time.monotonic()
    return _Driver


def _run(query: str, **params: Any) -> None:
    """执行 Cypher 写语句(无返回)。params 为绑定参数, 动态类型。"""
    driver = _get_driver()
    if driver is None:
        return
    try:
        from neo4j import Query

        with driver.session() as session:
            # Cypher 为运行时动态拼装, Query() 的 LiteralString 签名与动态 str 不兼容;
            # 驱动在运行时接受任意 str, 用 Any 中转显式满足静态签名。
            _ = session.run(cast(Query, cast(Any, query)), **params).consume()
    except Exception as e:  # noqa: BLE001
        logger.warning("Neo4j 同步失败(已降级): %s", e)


def sync_person(person_id: int, name: str, position: str = "", status: str = "active",
                company_id: int | None = None, company_name: str = "",
                email: str = "", phone: str = "", is_active: bool = True,
                province: str = "", city: str = "", county: str = "") -> None:
    """人员(节点) + 所属单位关系。province/city/county 非空时挂 IN_REGION。"""
    _run(
        """
        MERGE (p:Person {person_id: $person_id})
        SET p.name = $name,
            p.position = $position,
            p.status = $status,
            p.company_id = $company_id,
            p.email = $email,
            p.phone = $phone,
            p.is_active = $is_active,
            p.updated_at = datetime()
        WITH p
        OPTIONAL MATCH (p)-[w:WORKS_AT]->(old:Company)
        DELETE w
        WITH p
        FOREACH (x IN CASE WHEN $company_id IS NOT NULL AND $company_name <> '' THEN [1] ELSE [] END |
            MERGE (c:Company {company_id: $company_id})
            SET c.name = $company_name, c.updated_at = datetime()
            MERGE (p)-[:WORKS_AT {name_zh: $rel_works_at}]->(c)
        )
        """,
        person_id=person_id, name=name, position=position, status=status,
        company_id=company_id, company_name=company_name,
        email=email, phone=phone, is_active=is_active,
        rel_works_at=RELATION_NAMES_ZH["WORKS_AT"],
    )
    # 区域挂载(与公司/项目一致)
    if province or city or county:
        _sync_region_for("person", person_id, name, province, city, county)


def remove_person(person_id: int) -> None:
    """人员被删除(软删)时: 移除节点及关联关系。"""
    _run(
        """
        MATCH (p:Person {person_id: $person_id})
        DETACH DELETE p
        """,
        person_id=person_id,
    )


def sync_company_colleagues(company_id: int, persons: list[dict]) -> None:
    """同一单位人员的「同事」关系(全量重建, 幂等)。

    persons: [{person_id, name}] — 该单位下全部在职人员。
    两两建立 COLLEAGUE 双向边(带 company_id 便于按单位清理)。
    同一单位叫「同事」, 同一项目才叫「合作过」。
    """
    if not persons:
        return
    _run(
        """
        MATCH (c:Company {company_id: $company_id})
        OPTIONAL MATCH (a0:Person)-[r0:COLLEAGUE {company_id: $company_id}]->(b0:Person)
        DELETE r0
        WITH c
        UNWIND $persons AS pa
        UNWIND $persons AS pb
        WITH c, pa, pb
        WHERE pa.person_id < pb.person_id
        MERGE (a:Person {person_id: pa.person_id})
        SET a.name = pa.name, a.updated_at = datetime()
        MERGE (b:Person {person_id: pb.person_id})
        SET b.name = pb.name, b.updated_at = datetime()
        MERGE (a)-[:COLLEAGUE {company_id: $company_id, name_zh: $rel_colleague}]->(b)
        MERGE (b)-[:COLLEAGUE {company_id: $company_id, name_zh: $rel_colleague}]->(a)
        """,
        company_id=company_id, persons=persons,
        rel_colleague=RELATION_NAMES_ZH["COLLEAGUE"],
    )


def sync_company(company_id: int, name: str, code: str = "", company_type: str = "",
                 province: str = "", city: str = "", county: str = "") -> None:
    """单位节点。province/city/county 非空时挂 IN_REGION。"""
    _run(
        """
        MERGE (c:Company {company_id: $company_id})
        SET c.name = $name,
            c.code = $code,
            c.company_type = $company_type,
            c.updated_at = datetime()
        """,
        company_id=company_id, name=name, code=code, company_type=company_type,
    )
    # 区域挂载(公司存 province/city 列)
    if province or city or county:
        _sync_region_for("company", company_id, name, province, city, county)


def remove_company(company_id: int) -> None:
    _run("MATCH (c:Company {company_id: $company_id}) DETACH DELETE c", company_id=company_id)


def sync_project(project_id: int, name: str, code: str = "", status: str = "active",
                 category: str = "", province: str = "", city: str = "", county: str = "") -> None:
    """项目节点。province/city/county 非空时挂 IN_REGION。"""
    _run(
        """
        MERGE (p:Project {project_id: $project_id})
        SET p.name = $name,
            p.code = $code,
            p.status = $status,
            p.category = $category,
            p.updated_at = datetime()
        """,
        project_id=project_id, name=name, code=code, status=status, category=category,
    )
    # 区域挂载(项目存 ext_attrs.province/city/county)
    if province or city or county:
        _sync_region_for("project", project_id, name, province, city, county)


def remove_project(project_id: int) -> None:
    _run("MATCH (p:Project {project_id: $project_id}) DETACH DELETE p", project_id=project_id)


def sync_project_members(project_id: int, members: list[dict]) -> None:
    """项目成员参与关系 + 同项目两两合作关系(全量重建, 幂等)。

    members: [{person_id, name, role, company_id, company_name}]
    """
    if not members:
        return
    # 1) 重建参与关系(OPTIONAL MATCH 保证无旧关系时后续仍执行)
    _run(
        """
        MATCH (proj:Project {project_id: $project_id})
        OPTIONAL MATCH (proj)<-[r:PARTICIPATES_IN]-(old:Person)
        DELETE r
        WITH proj
        UNWIND $members AS m
        MERGE (p:Person {person_id: m.person_id})
        SET p.name = m.name,
            p.company_id = m.company_id,
            p.updated_at = datetime()
        MERGE (p)-[rel:PARTICIPATES_IN {role: m.role, name_zh: $rel_participates}]->(proj)
        // 成员有任职单位时, 同步建立 WORKS_AT 任职关系(否则图谱缺任职边)
        FOREACH (x IN CASE WHEN m.company_id IS NOT NULL AND m.company_name <> '' THEN [1] ELSE [] END |
            MERGE (c:Company {company_id: m.company_id})
            SET c.name = m.company_name, c.updated_at = datetime()
            MERGE (p)-[:WORKS_AT {name_zh: $rel_works_at}]->(c)
        )
        """,
        project_id=project_id, members=members,
        rel_participates=RELATION_NAMES_ZH["PARTICIPATES_IN"],
        rel_works_at=RELATION_NAMES_ZH["WORKS_AT"],
    )
    # 2) 同项目合作关系: 仅不同单位(或一方无单位)的成员两两建立 COLLABORATED_WITH(双向)。
    #    同单位的成员已有「同事」关系, 不再建立「合作过」。
    _run(
        """
        MATCH (proj:Project {project_id: $project_id})
        MATCH (a:Person)-[:PARTICIPATES_IN]->(proj)
        MATCH (b:Person)-[:PARTICIPATES_IN]->(proj)
        WHERE a.person_id < b.person_id
          AND (a.company_id IS NULL OR b.company_id IS NULL OR a.company_id <> b.company_id)
        MERGE (a)-[r1:COLLABORATED_WITH {via_project_id: $project_id, name_zh: $rel_collab}]->(b)
        MERGE (b)-[r2:COLLABORATED_WITH {via_project_id: $project_id, name_zh: $rel_collab}]->(a)
        """,
        project_id=project_id,
        rel_collab=RELATION_NAMES_ZH["COLLABORATED_WITH"],
    )
    # 3) 清理该项目下失效的合作关系: 已不在同一项目的成员对, 或同单位成员对(同事关系已足够)
    _run(
        """
        MATCH (a:Person)-[r:COLLABORATED_WITH {via_project_id: $project_id}]->(b:Person)
        WHERE NOT EXISTS {
                MATCH (a)-[:PARTICIPATES_IN]->(proj:Project {project_id: $project_id})
                MATCH (b)-[:PARTICIPATES_IN]->(proj)
              }
           OR (a.company_id IS NOT NULL AND a.company_id = b.company_id)
        DELETE r
        """,
        project_id=project_id,
    )


def sync_project_companies(project_id: int, companies: list[dict]) -> None:
    """项目单位参与关系(全量重建, 幂等)。"""
    if not companies:
        return
    _run(
        """
        MATCH (proj:Project {project_id: $project_id})
        OPTIONAL MATCH (proj)<-[r:PARTICIPATES_IN]-(old:Company)
        DELETE r
        WITH proj
        UNWIND $companies AS c
        MERGE (co:Company {company_id: c.company_id})
        SET co.name = c.name, co.updated_at = datetime()
        MERGE (co)-[rel:PARTICIPATES_IN {role: c.role, name_zh: $rel_participates}]->(proj)
        """,
        project_id=project_id, companies=companies,
        rel_participates=RELATION_NAMES_ZH["PARTICIPATES_IN"],
    )


def sync_project_complete(project: ProjectLike, members: list | None = None,
                          companies: list | None = None) -> None:
    """项目全量同步: 节点 + 成员参与/合作 + 单位参与。"""
    ext = project.ext_attrs or {}
    sync_project(project.id, project.name, code=project.code or "",
                 status=project.status or "active",
                 category=ext.get("category", ""),
                 province=ext.get("province", ""),
                 city=ext.get("city", ""),
                 county=ext.get("county", ""))
    if members is not None:
        sync_project_members(project.id, members)
    if companies is not None:
        sync_project_companies(project.id, companies)


# ====================================================================
# 区域维度(Region 节点 + IN_REGION/BELONGS_TO) — 知识图谱开放域扩展
# ====================================================================

# 区域关系中文名(开放关系类型除预设 4 类外由 register_open_relation 动态注册)
RELATION_NAMES_ZH.update({
    "IN_REGION": "位于",
    "BELONGS_TO": "隶属于",
})


def sync_region(region: dict) -> None:
    """同步行政区划 Region 节点。

    region: {name, level(省/市/县), province, city, county}
    幂等: MERGE by name。
    """
    _run(
        """
        MERGE (r:Region {name: $name})
        SET r.level = $level,
            r.province = $province,
            r.city = $city,
            r.county = $county,
            r.updated_at = datetime()
        """,
        name=region.get("name", ""), level=region.get("level", "市"),
        province=region.get("province", "") or "", city=region.get("city", "") or "",
        county=region.get("county", "") or "",
    )


def sync_region_hierarchy(province: str, city: str = "", county: str = "") -> None:
    """同步三级区域层级关系: (县)-[:BELONGS_TO]->(市)-[:BELONGS_TO]->(省)。

    只同步实际存在的层级, 缺失的跳过。省节点名用省核心词(四川), 便于匹配。

    防自环: 同名地名(如 喀什 既是地区/州又是其下辖县市)在 REGION_COUNTIES 中
    市/县共用同一核心词, 此时 city==county, 若照常建边会得到 (喀什)-[:BELONGS_TO]->(喀什) 自环。
    处理: city==province / county==city 时跳过对应层级与边, 只保留一个 Region 节点。
    """
    if not province:
        return
    sync_region({"name": province, "level": "省", "province": province, "city": "", "county": ""})
    if city and city != province:
        sync_region({"name": city, "level": "市", "province": province, "city": city, "county": ""})
        _run(
            "MATCH (c:Region {name: $city}), (p:Region {name: $province}) "  # pyright: ignore[reportImplicitStringConcatenation]
            "MERGE (c)-[:BELONGS_TO {name_zh: $rel}]->(p)",
            city=city, province=province, rel=RELATION_NAMES_ZH["BELONGS_TO"],
        )
    if county and city and county != city and county != province:
        sync_region({"name": county, "level": "县", "province": province, "city": city, "county": county})
        _run(
            "MATCH (c:Region {name: $county}), (p:Region {name: $city}) "  # pyright: ignore[reportImplicitStringConcatenation]
            "MERGE (c)-[:BELONGS_TO {name_zh: $rel}]->(p)",
            county=county, city=city, rel=RELATION_NAMES_ZH["BELONGS_TO"],
        )


def _sync_region_for(entity_type: str, entity_id: int, entity_name: str,
                     province: str, city: str, county: str) -> None:
    """同步函数内统一区域挂载入口: 原始省市县 → resolve_region 归一化 → sync_entity_region。

    供 sync_company/sync_project/sync_person 调用; 非目标省份(unmatched)自动跳过。
    """
    try:
        from app.services.china_regions import resolve_region
        region = resolve_region(province or "", city or "", county or "")
        if region.get("matched"):
            sync_entity_region(entity_type, entity_id, entity_name, region)
    except Exception as e:  # noqa: BLE001
        logger.warning("区域挂载失败(%s %s): %s", entity_type, entity_id, e)


def sync_entity_region(entity_type: str, entity_id: int, entity_name: str,
                       region: dict) -> None:
    """实体(公司/人员/项目) 挂载到 Region: (Entity)-[:IN_REGION]->(Region)。

    entity_type: company|person|project; entity_id/entity_name: 实体标识;
    region: {province, city, county} 三级(由 china_regions.resolve_region 产出)。
    """
    if not region or not region.get("matched"):
        return
    province = region.get("province", "")
    city = region.get("city", "")
    county = region.get("county", "")
    if not province and not city and not county:
        return
    # 同步区域节点与层级
    sync_region_hierarchy(province, city, county)
    # 实体挂 IN_REGION(挂最具体一级: 县→市→省)
    if entity_type == "company":
        label = "Company"
        key = "company_id"
    elif entity_type == "person":
        label = "Person"
        key = "person_id"
    else:
        label = "Project"
        key = "project_id"
    anchor = county or city or province
    if not anchor:
        return
    _run(
        f"""
        MATCH (e:{label} {{{key}: $entity_id}})
        MATCH (r:Region {{name: $anchor}})
        MERGE (e)-[:IN_REGION {{name_zh: $rel, entity_type: $entity_type, entity_name: $entity_name}}]->(r)
        """,
        entity_id=entity_id, entity_name=entity_name, anchor=anchor,
        rel=RELATION_NAMES_ZH["IN_REGION"], entity_type=entity_type,
    )


def register_open_relation(relation_key: str, relation_zh: str) -> None:
    """开放域关系注册: 把知识抽取发现的新关系类型加入 RELATION_NAMES_ZH(运行时动态)。

    关系类型由 LLM 开放输出(如 SUPPLIES_TO/SUBORDINATE_TO), 首次出现时自动注册中文名,
    供图谱查询/AI 分析自解释。
    """
    if not relation_key:
        return
    if relation_key not in RELATION_NAMES_ZH:
        RELATION_NAMES_ZH[relation_key] = relation_zh or relation_key
        logger.info("注册开放关系类型: %s -> %s", relation_key, RELATION_NAMES_ZH[relation_key])


def sync_open_relation(source_type: str, source_id: int, source_name: str,
                       target_type: str, target_id: int, target_name: str,
                       relation_key: str, relation_zh: str,
                       confidence: float = 0.8, evidence: str = "") -> None:
    """开放域关系落库: (source)-[:RELATION]->(target), 带证据与置信度。

    关系类型动态创建(Neo4j 关系类型名直接用 relation_key 大写)。
    """
    if not source_id or not target_id or source_id == target_id:
        return
    register_open_relation(relation_key, relation_zh)
    src_label, src_key = _entity_label_key(source_type)
    tgt_label, tgt_key = _entity_label_key(target_type)
    if not src_label or not tgt_label:
        return
    rel_type = relation_key.upper().replace("-", "_")
    _run(
        f"""
        MATCH (s:{src_label} {{{src_key}: $source_id}})
        MATCH (t:{tgt_label} {{{tgt_key}: $target_id}})
        MERGE (s)-[r:{rel_type}]->(t)
        SET r.name_zh = $relation_zh,
            r.source_name = $source_name,
            r.target_name = $target_name,
            r.confidence = $confidence,
            r.evidence = $evidence,
            r.updated_at = datetime()
        """,
        source_id=source_id, target_id=target_id,
        source_name=source_name, target_name=target_name,
        relation_zh=relation_zh, confidence=confidence, evidence=evidence,
    )


def _entity_label_key(entity_type: str) -> tuple:
    """实体类型 → (Neo4j label, 唯一键属性)。"""
    mapping = {
        "company": ("Company", "company_id"),
        "person": ("Person", "person_id"),
        "project": ("Project", "project_id"),
    }
    return mapping.get(entity_type, ("", ""))
