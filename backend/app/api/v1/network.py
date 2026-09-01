"""人脉查询 API — 以当前登录用户为源节点, 通过 Neo4j 知识图谱查找通往目标人员的人脉路径。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.config import settings
from app.middleware.auth import get_current_user
from app.models.person import Person
from app.models.company import Company
from app.models.project import Project
from app.models.rbac import SysUser
from app.services.neo4j_sync import sync_person, sync_company_colleagues
from app.services.cache_service import cache_service

router = APIRouter(prefix="/network", tags=["人脉"])

# 关系类型 -> 中文说明(兜底, 优先读 Neo4j 关系上的 name_zh)
RELATION_LABELS = {
    "WORKS_AT": "任职于",
    "PARTICIPATES_IN": "参与项目",
    "COLLABORATED_WITH": "合作过",
    "COLLEAGUE": "同事",
    "KNOWN": "认识",
    "OWNED_BY": "控股",
    "ADMIN_BY": "管理",
    "RESPONSIBLE_FOR": "负责",
    "GRANTED_ACCESS": "被授权查看",
}

# 系统授权类关系(非业务事实): AI 上下文分析时须标注为「系统授权」而非真实业务关系
_GRANT_RELATIONS = ("RESPONSIBLE_FOR", "GRANTED_ACCESS")


_driver = None  # 模块级单例 driver, 复用 Neo4j 连接池(避免每次请求重建连接)


def _get_driver():
    """惰性创建并复用 Neo4j driver(连接池), 提升并发性能。

    连接失败时抛出异常并重置单例, 下次请求重新创建, 避免坏 driver 永久缓存。
    """
    global _driver
    if _driver is None:
        if not settings.NEO4J_URI:
            raise HTTPException(status_code=503, detail="Neo4j 未配置")
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            connection_timeout=10,
            max_connection_pool_size=20,
        )
        try:
            # 显式验证连通性: 失败抛异常, 单例保持 None 可重试
            driver.verify_connectivity()
        except Exception:  # noqa: BLE001
            try:
                driver.close()
            except Exception:  # noqa: BLE001
                pass
            raise
        _driver = driver
    return _driver


def _reset_driver():
    """Neo4j 运行中故障时重置单例, 使下次请求可重新建立连接。"""
    global _driver
    if _driver is not None:
        try:
            _driver.close()
        except Exception:  # noqa: BLE001
            pass
    _driver = None


@router.get("/me")
def network_me(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """当前登录用户关联的人员(人脉源节点)完整信息。"""
    person_id = user.get("person_id")
    if not person_id:
        return {
            "person_id": None, "linked": False,
            "message": "尚未录入个人信息, 请先在「我的信息」中录入",
        }
    p = db.execute(
        select(Person).where(Person.id == person_id, Person.is_deleted == False)
    ).scalar_one_or_none()
    if not p:
        return {
            "person_id": person_id, "linked": False,
            "message": "关联人员不存在",
        }
    company_name = ""
    if p.company_id:
        company_name = db.execute(
            select(Company.name).where(Company.id == p.company_id, Company.is_deleted == False)
        ).scalar_one_or_none() or ""
    return {
        "person_id": p.id,
        "linked": True,
        "message": None,
        "name": p.name,
        "position": p.position or "",
        "company_id": p.company_id,
        "company_name": company_name,
        "email": p.email or "",
        "phone": p.phone or "",
        "status": p.status or "active",
    }


@router.post("/me")
async def network_me_save(
    body: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """录入/更新「我」的信息 — 创建或更新关联人员, 并作为 Neo4j 人脉源节点。"""
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="姓名必填")
    position = (body.get("position") or "").strip()
    company_id = body.get("company_id")
    email = (body.get("email") or "").strip()
    phone = (body.get("phone") or "").strip()
    status = body.get("status") or "active"

    su = db.execute(select(SysUser).where(SysUser.id == user["user_id"])).scalar_one()
    person_id = user.get("person_id")

    company_name = ""
    comp_province, comp_city = "", ""
    if company_id:
        crow = db.execute(
            select(Company.name, Company.province, Company.city)
            .where(Company.id == company_id, Company.is_deleted == False)
        ).first()
        if crow:
            company_name = crow[0] or ""
            comp_province, comp_city = crow[1] or "", crow[2] or ""

    old_company_id = None
    if person_id:
        p = db.execute(
            select(Person).where(Person.id == person_id, Person.is_deleted == False)
        ).scalar_one_or_none()
        if not p:
            raise HTTPException(status_code=404, detail="关联人员不存在")
        old_company_id = p.company_id
    else:
        # 自动生成唯一编码
        cnt = db.execute(select(Person).where(Person.name == name)).scalars().all()
        code = f"P{int(len(cnt)) + int(user['user_id']) + 1:04d}"
        p = Person(code=code, name=name, is_active=True)
        db.add(p)

    p.name = name
    p.position = position
    p.company_id = company_id
    p.email = email
    p.phone = phone
    p.status = status
    db.commit()
    db.refresh(p)

    # 关联用户与人员(新录时绑定)
    if not person_id:
        su.person_id = p.id
        db.commit()
    # 清除权限缓存, 使 get_current_user 下次读取到新的 person_id
    await cache_service.invalidate_user_permissions(user["user_id"])

    # ★ 同步 Neo4j 源节点
    try:
        sync_person(
            person_id=p.id, name=p.name or "", position=p.position or "",
            status=p.status or "active", company_id=p.company_id, company_name=company_name,
            email=p.email or "", phone=p.phone or "", is_active=True,
            province=comp_province, city=comp_city,
        )
    except Exception:  # noqa: BLE001
        pass
    # ★ 重建同事关系: 同单位人员两两建立 COLLEAGUE(录入/更新/调岗后, 旧单位与新单位都要重建)
    try:
        from app.api.v1.persons import _company_persons
        for cid in {company_id, old_company_id}:
            if not cid:
                continue
            plist = _company_persons(db, cid)
            if len(plist) >= 2:
                sync_company_colleagues(cid, plist)
    except Exception:  # noqa: BLE001
        pass

    return {
        "person_id": p.id,
        "linked": True,
        "message": None,
        "name": p.name,
        "position": p.position or "",
        "company_id": p.company_id,
        "company_name": company_name,
        "email": p.email or "",
        "phone": p.phone or "",
        "status": p.status or "active",
    }


@router.get("/path/{target_person_id}")
def network_path(
    target_person_id: int,
    max_depth: int = Query(6, ge=1, le=10),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """从当前登录用户(源)到目标人员的 Neo4j 最短路径(人脉链)。"""
    source_person_id = user.get("person_id")
    if not source_person_id:
        raise HTTPException(status_code=400, detail="当前用户未关联人员, 无法查找人脉")

    target = db.execute(
        select(Person).where(Person.id == target_person_id, Person.is_deleted == False)
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="目标人员不存在")

    # 源 == 目标: 直接返回
    if source_person_id == target_person_id:
        return {
            "source": {"person_id": source_person_id},
            "target": {"person_id": target_person_id, "name": target.name},
            "found": True,
            "steps": [
                {"type": "Person", "person_id": source_person_id, "name": "我", "relation": None},
                {"type": "Person", "person_id": target_person_id, "name": target.name, "relation": "本人"},
            ],
        }

    rec = _find_path(db, source_person_id, "Person", target_person_id, "Person", max_depth, target.name)

    if not rec:
        return {
            "source": {"person_id": source_person_id},
            "target": {"person_id": target_person_id, "name": target.name},
            "found": False,
            "steps": [],
            "message": f"未找到从你到「{target.name}」的人脉路径(可能无任何关联)",
        }

    steps = _assemble_steps(rec, db)

    return {
        "source": {"person_id": source_person_id},
        "target": {"person_id": target_person_id, "name": target.name},
        "found": True,
        "steps": steps,
    }


@router.get("/person-neighbors/{person_id}")
def network_person_neighbors(
    person_id: int,
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """获取某人在知识图谱中的直接邻居(1跳): 任职单位 / 参与项目 / 认识或共事过的人。

    用途: 作为 AI 分析的上下文节点补充——即使 MySQL 中该人无单位/无项目轨迹,
    也能从图谱拿到其真实关联(认识的人、同事、合作过的项目), 避免 AI 输出空洞。
    返回: { person_id, neighbors: [{type, name, relation_label, ...}] }
    """
    person = db.execute(
        select(Person).where(Person.id == person_id, Person.is_deleted == False)
    ).scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="人员不存在")

    # 排除当前登录用户(「我」): 上下文分析中不应把「我」作为目标人员(李四)的邻居节点,
    # 否则 AI 会误判「我」与目标有共同项目/合作(即使历史合作已结束)。
    me_names = {
        n for n in (str(user.get("display_name") or ""), str(user.get("username") or ""))
        if n and n != "-"
    }

    nodes: list[dict] = []
    try:
        driver = _get_driver()
        with driver.session() as s:
            # 该人员的 1 跳关联(不限方向), 排除自身 与 当前登录用户(「我」);
            # 授权边若已过期(expire_at 早于当前时间)不返回, 避免把过期授权当有效关联
            result = s.run(
                """
                MATCH (p:Person {person_id: $pid})-[r]-(n)
                WHERE NOT (n:Person AND (n.person_id = $pid OR n.name IN $me_names))
                  AND NOT (r.expire_at IS NOT NULL AND datetime(r.expire_at) < datetime())
                RETURN labels(n)[0] AS ntype, n AS node, type(r) AS rel, r.name_zh AS rel_zh
                LIMIT $lim
                """,
                pid=person_id, me_names=list(me_names) or [""], lim=limit,
            )
            for rec in result:
                n = rec["node"]
                ntype = rec["ntype"]
                rel = rec["rel"]
                rel_zh = rec["rel_zh"] or ""
                item = {"type": ntype, "name": n.get("name", "")}
                # 系统授权关系标记: 非业务事实(权限分发产生), AI 分析不得当作任职/参与
                if rel in _GRANT_RELATIONS:
                    item["grant"] = True
                    item["grant_label"] = rel_zh or RELATION_LABELS.get(rel, rel)
                if ntype == "Company":
                    item.update({
                        "relation_label": rel_zh or "任职于",
                        "company_name": n.get("name", ""),
                        "company_type": n.get("company_type", ""),
                        "company_id": n.get("company_id"),
                    })
                elif ntype == "Project":
                    item.update({
                        "relation_label": rel_zh or "参与项目",
                        "status": n.get("status", ""),
                        "category": n.get("category", ""),
                        "project_id": n.get("project_id"),
                    })
                elif ntype == "Person":
                    item.update({
                        "relation_label": rel_zh or RELATION_LABELS.get(rel, rel),
                        "position": n.get("position", ""),
                        "company_name": n.get("company_name", ""),
                        "person_id": n.get("person_id"),
                    })
                nodes.append(item)
    except Exception as e:  # noqa: BLE001
        _reset_driver()
        raise HTTPException(status_code=503, detail=f"Neo4j 不可用: {e}")

    return {
        "person_id": person_id,
        "person_name": person.name,
        "neighbors": nodes,
    }


@router.get("/path-to-company/{company_id}")
def network_path_to_company(
    company_id: int,
    max_depth: int = Query(6, ge=1, le=10),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """从当前登录用户(源)到目标公司(Company)的 Neo4j 最短路径(人脉链)。

    目标为公司节点; 与「到人」不同, 到公司的路径通常形如:
      我 → 项目 → 该公司(参与关系), 或 我 → 项目 → 该公司员工 → 该公司(任职关系)。
    优先选择含中间人员的路径(便于 AI 分析关键桥接人)。
    """
    source_person_id = user.get("person_id")
    if not source_person_id:
        raise HTTPException(status_code=400, detail="当前用户未关联人员, 无法查找人脉")

    target = db.execute(
        select(Company).where(Company.id == company_id, Company.is_deleted == False)
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="目标单位不存在")

    # 源(我)若任职于目标公司, 视为零跳直达
    my_company_id = db.execute(
        select(Person.company_id).where(Person.id == source_person_id)
    ).scalar_one_or_none()
    if my_company_id == company_id:
        return {
            "source": {"person_id": source_person_id},
            "target": {"company_id": company_id, "name": target.name},
            "found": True,
            "steps": [
                {"type": "Person", "person_id": source_person_id, "name": "我", "relation": None},
                {"type": "Company", "id": company_id, "name": target.name, "relation": "WORKS_AT", "relation_label": "任职于"},
            ],
        }

    rec = _find_path(db, source_person_id, "Person", company_id, "Company", max_depth, target.name)

    if not rec:
        return {
            "source": {"person_id": source_person_id},
            "target": {"company_id": company_id, "name": target.name},
            "found": False,
            "steps": [],
            "message": f"未找到从你到「{target.name}」的人脉路径(可能无任何关联)",
        }

    steps = _assemble_steps(rec, db)

    return {
        "source": {"person_id": source_person_id},
        "target": {"company_id": company_id, "name": target.name},
        "found": True,
        "steps": steps,
    }


_NODE_KEY = {"Person": "person_id", "Company": "company_id", "Project": "project_id"}


@router.get("/graph/company/{company_id}")
def network_graph_company(
    company_id: int,
    max_depth: int = Query(2, ge=1, le=3),
    limit: int = Query(200, ge=20, le=500),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """以某公司为中心的知识图谱子图(多跳节点 + 关系), 用于前端可视化。

    返回结构: { center, nodes:[{id,label,name,group}], links:[{source,target,type,label}] }
    - label: Person / Company / Project
    - group: 用于前端着色(公司自身 / 关联单位 / 人员 / 项目)
    - 节点与关系数量上限由 limit 控制, 避免超大子图
    """
    target = db.execute(
        select(Company).where(Company.id == company_id, Company.is_deleted == False)
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="目标单位不存在")

    partner_rows: list = []
    try:
        driver = _get_driver()
        with driver.session() as session:
            depth_clause = f"[*..{max_depth}]"
            # 取以该公司为中心向外 max_depth 跳的节点与关系。
            # 节点 id 用类型前缀(Person/Company/Project) + 各自 id, 避免不同类型 id 数值冲突(ECharts 要求 id 唯一)。
            cypher = f"""
                MATCH (c:Company {{company_id: $cid}})
                MATCH p = (c)-{depth_clause}-(n)
                WITH nodes(p) AS ns
                UNWIND ns AS n
                WITH DISTINCT n
                LIMIT $limit
                WITH collect(n) AS kept
                UNWIND kept AS kn
                OPTIONAL MATCH (kn)-[r]-(other)
                WHERE other IN kept
                WITH kept,
                     [n IN kept | {{
                       id: CASE labels(n)[0]
                             WHEN 'Person' THEN 'P' + toString(n.person_id)
                             WHEN 'Company' THEN 'C' + toString(n.company_id)
                             WHEN 'Project' THEN 'J' + toString(n.project_id)
                             ELSE toString(coalesce(n.person_id, n.company_id, n.project_id))
                           END,
                       label: labels(n)[0],
                       name: coalesce(n.name, n.code, ''),
                       position: coalesce(n.position, ''),
                       company_id: n.company_id,
                       is_center: (labels(n)[0] = 'Company' AND n.company_id = $cid)
                     }}] AS nodes,
                     collect({{
                       source: CASE labels(kn)[0]
                                 WHEN 'Person' THEN 'P' + toString(kn.person_id)
                                 WHEN 'Company' THEN 'C' + toString(kn.company_id)
                                 WHEN 'Project' THEN 'J' + toString(kn.project_id)
                                 ELSE toString(coalesce(kn.person_id, kn.company_id, kn.project_id))
                               END,
                       target: CASE labels(other)[0]
                                 WHEN 'Person' THEN 'P' + toString(other.person_id)
                                 WHEN 'Company' THEN 'C' + toString(other.company_id)
                                 WHEN 'Project' THEN 'J' + toString(other.project_id)
                                 ELSE toString(coalesce(other.person_id, other.company_id, other.project_id))
                               END,
                       type: type(r),
                       label: coalesce(r.name_zh, '')
                     }}) AS rawLinks
                RETURN nodes, rawLinks AS links
            """
            result = session.run(cypher, cid=company_id, limit=limit)
            rec = result.single()

            # 合作单位聚合查询(人员口径为主): 中心公司内部人员参与的公共项目 → 该项目的
            # 其他参与人(非本公司) → 其任职公司(WORKS_AT) = 合作单位。
            # 关键: 不依赖 (Company)-[:PARTICIPATES_IN]->(Project) 公司级参与关系——
            # 该关系只在「项目单位」维护时同步, 历史数据普遍缺失(公司级出边为空)。
            # 参与关系实际绑在「人」上, 从人员公共项目推导合作方才完整可靠。
            # 同时保留公司级参与项目作为补充路径(EXISTS 任一路径即可)。
            # 返回: 合作单位列表(含该单位的内部联系人及合作项目)。
            partner_cypher = f"""
                MATCH (c:Company {{company_id: $cid}})
                MATCH (proj:Project)
                WHERE EXISTS {{
                    MATCH (c)<-[:WORKS_AT]-(mine:Person)-[:PARTICIPATES_IN]->(proj)
                }} OR EXISTS {{
                    MATCH (c)-[:PARTICIPATES_IN]->(proj)
                }}
                MATCH (proj)<-[:PARTICIPATES_IN]-(p:Person)
                WHERE NOT (p:Person)-[:WORKS_AT]->(c)
                OPTIONAL MATCH (p:Person)-[w:WORKS_AT]->(pc:Company)
                WITH pc, proj, p
                WHERE pc IS NOT NULL
                ORDER BY proj.project_id, p.person_id
                WITH pc,
                     collect(DISTINCT {{
                       id: proj.project_id,
                       name: proj.name
                     }}) AS projects,
                     collect(DISTINCT {{
                       id: 'P' + toString(p.person_id),
                       name: coalesce(p.name, ''),
                       position: coalesce(p.position, ''),
                       company_id: pc.company_id
                     }}) AS persons
                RETURN 'C' + toString(pc.company_id) AS id,
                       pc.company_id AS company_id,
                       coalesce(pc.name, '') AS name,
                       projects,
                       persons
                ORDER BY name
            """
            partner_result = session.run(partner_cypher, cid=company_id)
            partner_rows = [dict(r) for r in partner_result]
    except Exception as e:  # noqa: BLE001
        _reset_driver()
        raise HTTPException(status_code=503, detail=f"Neo4j 不可用: {e}")

    nodes = rec["nodes"] if rec else []
    raw_links = rec["links"] if rec else []

    # 合作单位(按单位口径聚合): 中心单位项目参与者的任职公司
    partner_companies = partner_rows

    # 给节点补充 group(用于前端着色)
    for n in nodes:
        if n.get("is_center"):
            n["group"] = "center"
        elif n["label"] == "Company":
            n["group"] = "company"
        elif n["label"] == "Project":
            n["group"] = "project"
        else:
            n["group"] = "person"

    # 关系去重: 同 (source, target, type) 只保留一条, 且 source != target
    links = []
    seen = set()
    for l in raw_links:
        if not l.get("source") or not l.get("target"):
            continue
        if l["source"] == l["target"]:
            continue
        key = (l["source"], l["target"], l["type"])
        if key in seen:
            continue
        seen.add(key)
        links.append({
            "source": l["source"],
            "target": l["target"],
            "type": l["type"],
            "label": l["label"],
        })

    return {
        "center": {"company_id": company_id, "name": target.name},
        "nodes": nodes,
        "links": links,
        "partner_companies": partner_companies,
        "stats": {"nodes": len(nodes), "links": len(links), "partners": len(partner_companies), "max_depth": max_depth},
    }


def _find_path(db: Session, src_id: int, src_label: str,
               tgt_id: int, tgt_label: str, max_depth: int, tgt_name: str):
    """Neo4j 最短路径查询(共享实现)。优先选择含「同事」关系 / 含中间人员的路径。"""
    # 按节点标签选择匹配属性: Person→person_id, Company→company_id, Project→project_id。
    # 源始终为当前用户(Person)。
    src_key = "person_id"
    tgt_key = _NODE_KEY.get(tgt_label, "person_id")
    try:
        driver = _get_driver()
        with driver.session() as session:
            # 注意: Neo4j 的 shortestPath 不支持变量深度参数, 需内联数值(已做 int 校验, 无注入风险)。
            depth_clause = f"[*..{max_depth}]"
            result = session.run(
                f"""
                MATCH (src:{src_label} {{{src_key}: $src}})
                MATCH (tgt:{tgt_label} {{{tgt_key}: $tgt}})
                // 人脉路径只经过 人员/单位/项目, 排除 Region 节点(区域仅作参考, 不作人脉一跳)
                MATCH p = allShortestPaths((src)-{depth_clause}-(tgt))
                WHERE NONE(n IN nodes(p) WHERE n:Region)
                RETURN p,
                       [n IN nodes(p) | labels(n)[0]] AS labels,
                       [n IN nodes(p) | coalesce(n.name, n.code, '')] AS names,
                       [n IN nodes(p) | coalesce(n.person_id, n.company_id, n.project_id)] AS ids,
                       [n IN nodes(p) | coalesce(n.company_type, '')] AS company_types,
                       [r IN relationships(p) | type(r)] AS rels,
                       [r IN relationships(p) | r.name_zh] AS rels_zh,
                       [r IN relationships(p) | coalesce(r.role, '')] AS rel_roles,
                       [r IN relationships(p) | coalesce(r.via_project_id, 0)] AS via_project_ids,
                       [r IN relationships(p) | coalesce(r.company_id, 0)] AS rel_company_ids,
                       size([r IN relationships(p) WHERE type(r) = 'COLLEAGUE']) AS collab_pri,
                       size([n IN nodes(p) WHERE labels(n)[0] = 'Person']) AS person_count,
                       length(p) AS len
                ORDER BY len ASC, person_count DESC, collab_pri DESC
                LIMIT 1
                """,
                src=src_id, tgt=tgt_id,
            )
            return result.single()
    except Exception as e:  # noqa: BLE001
        _reset_driver()
        raise HTTPException(status_code=503, detail=f"Neo4j 不可用: {e}")


def _assemble_steps(rec, db: Session):
    """将 Neo4j 查询结果组装为前端步骤数组(共享实现)。"""
    labels = rec["labels"]
    names = rec["names"]
    ids = rec["ids"]
    rels = rec["rels"]
    rels_zh = rec["rels_zh"]
    rel_roles = rec["rel_roles"]
    via_project_ids = rec["via_project_ids"]
    rel_company_ids = rec["rel_company_ids"]

    # ── MySQL 补齐: 项目名 / 单位名 / 人员职位 ──
    all_project_ids = set(p for p in via_project_ids if p)
    all_project_ids.update(ids[i] for i, t in enumerate(labels) if t == "Project")
    proj_names: dict = {}
    if all_project_ids:
        for pid, nm, status_, cat in db.execute(
            select(Project.id, Project.name, Project.status, Project.ext_attrs)
            .where(Project.id.in_(all_project_ids))
        ):
            proj_names[pid] = {
                "name": nm,
                "status": status_ or "",
                "category": (cat or {}).get("category", "") if isinstance(cat, dict) else "",
            }

    all_company_ids = set(c for c in rel_company_ids if c)
    all_company_ids.update(ids[i] for i, t in enumerate(labels) if t == "Company")

    # 先查路径上所有 Person 的 company_id, 并入公司名集合,
    # 否则人员有单位但路径没经过 Company 节点时 company_name 会查不到(变空)。
    person_ids = [ids[i] for i, t in enumerate(labels) if t == "Person"]
    person_infos: dict = {}
    if person_ids:
        for pid, position, company_id in db.execute(
            select(Person.id, Person.position, Person.company_id)
            .where(Person.id.in_(person_ids), Person.is_deleted == False)
        ):
            person_infos[pid] = {"position": position or "", "company_id": company_id}
            if company_id:
                all_company_ids.add(company_id)

    company_names: dict = {}
    if all_company_ids:
        for cid, nm in db.execute(
            select(Company.id, Company.name)
            .where(Company.id.in_(all_company_ids), Company.is_deleted == False)
        ):
            company_names[cid] = nm

    # ── 组装 steps ──
    steps = []
    for i, label in enumerate(labels):
        relation = None
        relation_label = ""
        rel_role = ""
        rel_via_project = ""
        via_project_id = None
        rel_company = ""
        if i > 0:
            relation = rels[i - 1]
            # 优先取 Neo4j 关系上的中文属性(name_zh), 兼容旧数据回退映射表
            relation_label = rels_zh[i - 1] or RELATION_LABELS.get(relation or "", relation or "")
            rel_role = rel_roles[i - 1] or ""
            if via_project_ids[i - 1]:
                info = proj_names.get(via_project_ids[i - 1])
                rel_via_project = info["name"] if info else ""
                via_project_id = via_project_ids[i - 1]
            else:
                via_project_id = None
            if rel_company_ids[i - 1]:
                rel_company = company_names.get(rel_company_ids[i - 1], "")

        step: dict = {
            "type": label,
            "id": ids[i],
            # 首节点即当前登录用户本人(源), 统一显示为「我」, 保证 AI 提示词中
            # me_name 与 nodes[0] 一致, 避免模型把「我」和源节点误认为两个人。
            "name": "我" if i == 0 else names[i],
            "relation": relation,
            "relation_label": relation_label,
            "rel_role": rel_role,
            "rel_via_project": rel_via_project,
            "via_project_id": via_project_id,
            "rel_company": rel_company,
            "position": "",
            "company_name": "",
            "company_type": "",
            "category": "",
            "status": "",
        }
        if label == "Person" and ids[i] in person_infos:
            pi = person_infos[ids[i]]
            step["position"] = pi["position"]
            if pi["company_id"]:
                step["company_name"] = company_names.get(pi["company_id"], "")
        elif label == "Company":
            step["company_type"] = rec["company_types"][i] or ""
        elif label == "Project":
            info = proj_names.get(ids[i], {})
            step["category"] = info.get("category", "")
            step["status"] = info.get("status", "")
        steps.append(step)

    return steps
