"""人脉库核心服务 — 从多源聚合关系、推导专长、初始化、招标匹配。

数据源(只读聚合, 不重复存原始数据):
  - project_member: 人员↔项目(角色 manager/member/业主联系人)
  - project_company: 单位↔项目(角色 constructor/owner/designer/supervisor/partner)
  - bid_notice: 采购人/中标供应商(近两年)
  - entity_relation: LLM 开放三元组
  - person_skill: 人员专长(手工 + 项目类别推导)

输出:
  - network_edge: 两实体加权关系边(可溯源)
  - tender_match: 招标/意向线索 × 人脉实体 匹配推荐
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, delete, update
from sqlalchemy.orm import Session

from app.models.business_network import PersonSkill, NetworkEdge, TenderMatch
from app.models.person import Person
from app.models.company import Company
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.company import ProjectCompany
from app.models.bid_notice import BidNotice
from app.models.entity_relation import EntityRelation

logger = logging.getLogger("business_network")

# 项目角色中文
_PROJECT_ROLE_ZH = {
    "manager": "项目负责人", "member": "项目成员", "owner": "业主联系人",
    "constructor": "施工单位", "owner_unit": "业主单位", "designer": "设计单位",
    "supervisor": "监理单位", "partner": "合作单位",
}

# 近两年窗口
TWO_YEARS = timedelta(days=730)


def _person_of(db: Session, pid: int) -> Optional[Person]:
    return db.get(Person, pid)


def _company_of(db: Session, cid: int) -> Optional[Company]:
    return db.get(Company, cid)


def _project_of(db: Session, pid: int) -> Optional[Project]:
    return db.get(Project, pid)


# ---------------------------------------------------------------------------
# ① 关系聚合: 各源 → network_edge(去重合并, 权重累加)
# ---------------------------------------------------------------------------
def rebuild_edges(db: Session) -> dict:
    """从全部数据源重建 network_edge(幂等: 清空重建)。

    聚合关系:
      person-PARTICIPATES_IN-project(project_member)
      company-PARTICIPATES_IN-project(project_company)
      person-WORKS_AT-company(project_member 的 company_id / person.company_id)
      company-COLLABORATED_WITH-company(同项目不同角色, 同项目共事的单位)
      person-COLLABORATED_WITH-person(同项目成员)
      company-COLLABORATED_WITH-person(同项目单位+人员)
      person-COMPETES_WITH-company / company-COMPETES_WITH-company(bid_notice 同场)
      company-WON_BID-project? 不建, bid 关系独立
    """
    db.execute(delete(NetworkEdge))
    counts = {"person_project": 0, "company_project": 0, "person_company": 0,
              "company_company": 0, "person_person": 0, "company_person": 0}

    # --- 人员↔项目 ---
    pms = db.execute(
        select(ProjectMember).where(ProjectMember.is_deleted == False)
    ).scalars().all()
    for pm in pms:
        person = _person_of(db, pm.person_id)
        project = _project_of(db, pm.project_id)
        if not person or not project:
            continue
        _upsert_edge(db, "person", pm.person_id, person.name or "",
                     "project", pm.project_id, project.name or "",
                     "PARTICIPATES_IN", _PROJECT_ROLE_ZH.get(pm.role or "member", pm.role or "参与"),
                     source="project_member", evidence=project.name or "")
        counts["person_project"] += 1

    # --- 单位↔项目 ---
    pcs = db.execute(
        select(ProjectCompany).where(ProjectCompany.is_deleted == False)
    ).scalars().all()
    for pc in pcs:
        comp = _company_of(db, pc.company_id)
        project = _project_of(db, pc.project_id)
        if not comp or not project:
            continue
        _upsert_edge(db, "company", pc.company_id, comp.name or "",
                     "project", pc.project_id, project.name or "",
                     "PARTICIPATES_IN", _PROJECT_ROLE_ZH.get(pc.role or "constructor", pc.role or "参与"),
                     source="project_company", evidence=project.name or "")
        counts["company_project"] += 1

    # --- 人员↔单位(任职) ---
    persons = db.execute(select(Person).where(Person.is_deleted == False)).scalars().all()
    for p in persons:
        if p.company_id:
            comp = _company_of(db, p.company_id)
            if comp:
                _upsert_edge(db, "person", p.id, p.name or "",
                             "company", p.company_id, comp.name or "",
                             "WORKS_AT", "任职于", source="person", evidence=comp.name or "")
                counts["person_company"] += 1

    # --- 同项目: 单位-单位 / 人员-人员 / 单位-人员 合作 ---
    for pc in pcs:
        comp = _company_of(db, pc.company_id)
        project = _project_of(db, pc.project_id)
        if not comp or not project:
            continue
        # 单位-单位(同项目其他角色单位)
        for pc2 in pcs:
            if pc2.project_id != pc.project_id or pc2.company_id == pc.company_id:
                continue
            comp2 = _company_of(db, pc2.company_id)
            if not comp2:
                continue
            _upsert_edge(db, "company", pc.company_id, comp.name or "",
                         "company", pc2.company_id, comp2.name or "",
                         "COLLABORATED_WITH", "合作过", source="project_company",
                         evidence=project.name or "")
            counts["company_company"] += 1
        # 单位-人员(该单位在该项目的人员)
        for pm in pms:
            if pm.project_id != pc.project_id:
                continue
            person = _person_of(db, pm.person_id)
            if not person:
                continue
            # 单位是该项目的角色单位, 项目成员与其共事
            _upsert_edge(db, "company", pc.company_id, comp.name or "",
                         "person", pm.person_id, person.name or "",
                         "COLLABORATED_WITH", "合作过", source="project_member",
                         evidence=project.name or "")
            counts["company_person"] += 1

    # --- 同项目: 人员-人员 合作(同项目成员互为同事) ---
    for pm in pms:
        person = _person_of(db, pm.person_id)
        if not person:
            continue
        for pm2 in pms:
            if pm2.project_id != pm.project_id or pm2.person_id == pm.person_id:
                continue
            person2 = _person_of(db, pm2.person_id)
            if not person2:
                continue
            _upsert_edge(db, "person", pm.person_id, person.name or "",
                         "person", pm2.person_id, person2.name or "",
                         "COLLABORATED_WITH", "合作过", source="project_member",
                         evidence=_project_of(db, pm.project_id).name if _project_of(db, pm.project_id) else "")
            counts["person_person"] += 1

    db.commit()
    logger.info("network_edge 重建完成: %s", counts)
    return counts


def _upsert_edge(db: Session, src_type, src_id, src_name, tgt_type, tgt_id, tgt_name,
                 rel_type, rel_zh, source="", evidence="", last_seen=None, weight=1.0):
    """幂等插入/更新人脉边(唯一键 src+tgt+rel)。"""
    if not src_id or not tgt_id or src_id == tgt_id:
        return
    now = datetime.now()
    edge = db.execute(
        select(NetworkEdge).where(
            NetworkEdge.src_type == src_type, NetworkEdge.src_id == src_id,
            NetworkEdge.tgt_type == tgt_type, NetworkEdge.tgt_id == tgt_id,
            NetworkEdge.rel_type == rel_type, NetworkEdge.is_deleted == False,
        ).limit(1)
    ).scalar_one_or_none()
    if edge:
        edge.weight = float(edge.weight) + weight
        edge.last_seen = now
        if evidence and evidence not in (edge.evidence or ""):
            edge.evidence = f"{edge.evidence}；{evidence}"[:1000]
    else:
        db.add(NetworkEdge(
            src_type=src_type, src_id=src_id, src_name=src_name[:500],
            tgt_type=tgt_type, tgt_id=tgt_id, tgt_name=tgt_name[:500],
            rel_type=rel_type, rel_zh=rel_zh, weight=weight,
            source=source, evidence=evidence[:1000], last_seen=now,
        ))
    db.flush()


# ---------------------------------------------------------------------------
# ② 人员专长: 手工 + 项目类别推导
# ---------------------------------------------------------------------------
# 项目类别 → 专长关键词(映射 project category 或 项目名关键词)
_CATEGORY_SKILLS = {
    "geo_survey": ["地质勘察", "岩土工程", "工程勘察"],
    "geo_hazard": ["地质灾害", "地灾治理", "滑坡治理"],
    "eco_restoration": ["生态修复", "环境治理"],
    "mining_rights": ["矿业权", "采矿"],
    "policy": ["政策研究", "规划咨询"],
}
_SKILL_KEYWORDS = [
    ("地质", "地质勘察"), ("勘察", "工程勘察"), ("岩土", "岩土工程"),
    ("地灾", "地质灾害"), ("滑坡", "滑坡治理"), ("生态修复", "生态修复"),
    ("环境治理", "环境治理"), ("测绘", "测绘"), ("监测", "监测"),
    ("矿业", "矿业权"), ("基坑", "基坑工程"), ("管道", "管网工程"),
]


def sync_person_skills(db: Session) -> dict:
    """同步人员专长: 手工标签保留; 从参与项目推导补全(幂等)。"""
    added = 0
    members = db.execute(
        select(ProjectMember).where(ProjectMember.is_deleted == False)
    ).scalars().all()
    for pm in members:
        project = _project_of(db, pm.project_id)
        if not project:
            continue
        skills = set()
        # 从项目类别
        ext = project.ext_attrs or {}
        cat = ext.get("category", "")
        skills.update(_CATEGORY_SKILLS.get(cat, []))
        # 从项目名关键词
        pname = project.name or ""
        for kw, skill in _SKILL_KEYWORDS:
            if kw in pname:
                skills.add(skill)
        for s in skills:
            exists = db.execute(
                select(PersonSkill).where(
                    PersonSkill.person_id == pm.person_id,
                    PersonSkill.skill == s, PersonSkill.is_deleted == False,
                ).limit(1)
            ).scalar_one_or_none()
            if not exists:
                db.add(PersonSkill(person_id=pm.person_id, skill=s,
                                   source="project_infer", confidence=0.7))
                added += 1
    db.commit()
    return {"added": added}


# ---------------------------------------------------------------------------
# ③ 初始化: 全量重建(edges + skills)
# ---------------------------------------------------------------------------
def init_network(db: Session) -> dict:
    """人脉库初始化: 重建人脉边 + 同步专长。幂等可重复执行。"""
    edge_stats = rebuild_edges(db)
    skill_stats = sync_person_skills(db)
    return {"edges": edge_stats, "skills": skill_stats}


# ---------------------------------------------------------------------------
# ④ 招标匹配: 招标/意向线索 × 人脉实体
# ---------------------------------------------------------------------------
def match_tenders(db: Session, clue_id: Optional[int] = None, limit: int = 100) -> dict:
    """把招标/意向线索(web_clue + intent_notice)与人员/单位匹配推荐。

    匹配逻辑(加权):
      - 专长匹配: 线索标题含人员专长(skill) → 人员 高优先级
      - 类别匹配: 线索标题含 项目类别关键词 → 相关人员/单位
      - 区域匹配: 线索地域与单位省份/城市一致
      - 单位匹配: 线索关键词命中单位业务关键词(company_type/行业)
      - 意向单位匹配: intent_notice.matched_entity.unit 直接匹配 company 库
    写入 tender_match 表(幂等: 同 clue/intent+entity 更新, intent_id 区分来源)。
    """
    from app.models.web_clue import WebClue
    from app.models.intent_notice import IntentNotice

    # 候选线索: 意向/招标类
    intent_kw = ("采购意向", "意向公开", "采购需求", "招标", "采购公告", "中标", "勘察", "地质灾害", "生态修复")
    stmt = select(WebClue).where(
        WebClue.is_deleted == False,
        WebClue.title != None,
    ).order_by(WebClue.id.desc()).limit(300)
    if clue_id:
        stmt = stmt.where(WebClue.id == clue_id)
    clues = db.execute(stmt).scalars().all()

    # 意向通知也参与匹配(intent_id 区分来源)
    istmt = select(IntentNotice).where(
        IntentNotice.is_deleted == False,
        IntentNotice.title != None,
    ).order_by(IntentNotice.id.desc()).limit(200)
    intents = db.execute(istmt).scalars().all()

    persons = db.execute(select(Person).where(Person.is_deleted == False)).scalars().all()
    companies = db.execute(select(Company).where(Company.is_deleted == False)).scalars().all()
    person_skills = {}
    for ps in db.execute(select(PersonSkill).where(PersonSkill.is_deleted == False)).scalars().all():
        person_skills.setdefault(ps.person_id, []).append(ps.skill)

    matched = 0
    now = datetime.now()

    def _match_one(title: str, region: str, amount: str, valid_until,
                   clue_id: Optional[int], intent_id: Optional[int]):
        nonlocal matched
        best_person, best_company = None, None
        best_p_score, best_c_score = 0.0, 0.0
        # 人员: 专长命中
        for p in persons:
            skills = person_skills.get(p.id, [])
            score = 0.0
            for s in skills:
                if s and s in title:
                    score += 0.6
            if score and p.company_id:
                comp = _company_of(db, p.company_id)
                if comp and region and (comp.province or "") and comp.province in region:
                    score += 0.2
            if score > best_p_score:
                best_p_score, best_person = score, p
        # 单位: 业务关键词匹配(company_type/行业)
        for c in companies:
            score = 0.0
            ctype = c.company_type or ""
            name = c.name or ""
            for kw in ("勘察", "施工", "设计", "监理"):
                if kw in ctype or kw in name:
                    if kw in title:
                        score += 0.5
            if region and (c.province or "") and c.province in region:
                score += 0.2
            if score > best_c_score:
                best_c_score, best_company = score, c

        if best_person and best_p_score >= 0.6:
            _upsert_tender_match(db, clue_id=clue_id, intent_id=intent_id, title=title,
                                 entity_type="person", entity_id=best_person.id,
                                 entity_name=best_person.name or "", match_type="skill",
                                 match_reason=f"专长匹配(得分{best_p_score:.2f})",
                                 score=best_p_score, region=region, amount=amount,
                                 valid_until=valid_until)
            matched += 1
        if best_company and best_c_score >= 0.6:
            _upsert_tender_match(db, clue_id=clue_id, intent_id=intent_id, title=title,
                                 entity_type="company", entity_id=best_company.id,
                                 entity_name=best_company.name or "", match_type="category",
                                 match_reason=f"业务匹配(得分{best_c_score:.2f})",
                                 score=best_c_score, region=region, amount=amount,
                                 valid_until=valid_until)
            matched += 1

    for clue in clues:
        title = clue.title or ""
        if not any(k in title for k in intent_kw):
            continue
        meta = clue.meta if isinstance(clue.meta, dict) else {}
        region = meta.get("regionName") or clue.region or ""
        amount = str(meta.get("budget") or "")
        valid_until = _compute_valid_until(meta, clue.published_at or clue.fetched_at or now)
        _match_one(title, region, amount, valid_until, clue_id=clue.id, intent_id=None)

    # 仅全局匹配(clue_id 未指定)时处理意向通知; 指定单条线索时只匹配该线索本身,
    # 否则 /biz-network/tenders/match?clue_id=X 会写入大量 clue_id=None 的意向行,
    # 导致前端按 clue_id 查询该标讯匹配时永远为空(P1-5 面板看似坏掉)。
    if clue_id is None:
        for it in intents:
            title = it.title or ""
            if not any(k in title for k in intent_kw):
                continue
            region = it.region or ""
            amount = str(int(it.amount)) if it.amount is not None else ""
            # 有效期: 发布时间+90天(意向公开有效期较长)
            valid_until = (it.published_at or now) + timedelta(days=90)
            _match_one(title, region, amount, valid_until, clue_id=None, intent_id=it.id)

    db.commit()
    return {"matched": matched, "candidates": len(clues) + len(intents)}


def _compute_valid_until(meta: dict, base: Optional[datetime] = None) -> Optional[datetime]:
    """计算推荐有效期截止。优先线索截止时间(expireTime), 否则基准时间+60天。

    meta.expireTime 常见格式: "2026-09-30 09:30" / "2026/9/30" / "2026-09-30T09:30:00"
    """
    expire = (meta or {}).get("expireTime") or (meta or {}).get("expire_time")
    if expire:
        s = str(expire).strip().replace("/", "-").replace("T", " ")
        s = s[:16]
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
    return (base or datetime.now()) + timedelta(days=60)


def refresh_match_validity(db: Session, now: Optional[datetime] = None) -> dict:
    """刷新全部招标匹配的有效期/过期标记(幂等)。

    规则: valid_until 为空 → 按创建时间+60天补算; 已过 valid_until → is_expired=True。
    供手动刷新(API)与定时清理任务共用。
    """
    now = now or datetime.now()
    matches = db.execute(
        select(TenderMatch).where(TenderMatch.is_deleted == False)
    ).scalars().all()
    expired = 0
    updated = 0
    for m in matches:
        if not m.valid_until:
            m.valid_until = (m.created_at or now) + timedelta(days=60)
            updated += 1
        expired_now = m.valid_until < now
        if expired_now != m.is_expired:
            m.is_expired = expired_now
            updated += 1
        if expired_now:
            expired += 1
    db.commit()
    return {"total": len(matches), "expired": expired, "updated": updated}


def _upsert_tender_match(db, clue_id=None, intent_id=None, title="", entity_type="person",
                         entity_id=0, entity_name="", match_type="skill", match_reason="",
                         score=0.0, region="", amount="", valid_until=None):
    """幂等写 tender_match(clue_id / intent_id 二选一, 唯一键区分来源)。"""
    conds = [
        TenderMatch.entity_type == entity_type,
        TenderMatch.entity_id == entity_id,
        TenderMatch.is_deleted == False,
    ]
    if intent_id is not None:
        conds.append(TenderMatch.intent_id == intent_id)
        conds.append(TenderMatch.clue_id.is_(None))
    else:
        conds.append(TenderMatch.clue_id == clue_id)
    exists = db.execute(
        select(TenderMatch).where(*conds).limit(1)
    ).scalar_one_or_none()
    if exists:
        exists.score = score
        exists.match_reason = match_reason
        if valid_until:
            exists.valid_until = valid_until
    else:
        db.add(TenderMatch(
            clue_id=clue_id, intent_id=intent_id, title=title[:500],
            entity_type=entity_type, entity_id=entity_id,
            entity_name=entity_name, match_type=match_type, match_reason=match_reason,
            score=score, region=region or None, amount=amount or None, status="new",
            valid_until=valid_until,
        ))
    db.flush()

    # 意向匹配实体 → Neo4j 建立 (Intent)-[:RELATES_TO]->(Person|Company) 边, 供意向专属子图
    if intent_id is not None and entity_id:
        try:
            from app.services import neo4j_sync as _nsync
            _nsync.register_open_relation("RELATES_TO", "相关于")
            _nsync.sync_intent(intent_id=intent_id, title=title)
            _nsync.sync_open_relation(
                source_type="intent", source_id=intent_id, source_name=title,
                target_type=entity_type, target_id=int(entity_id), target_name=entity_name,
                relation_key="RELATES_TO", relation_zh="相关于",
                confidence=min(1.0, float(score or 0.8)),
                evidence=f"意向匹配:{match_type}",
            )
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# 意向关联实体批量构建: 从意向标题/原文提取真实单位名/人名, 关联到存量公司/人员
# ---------------------------------------------------------------------------
# 单位名后缀(用于从意向标题/正文提取「业主/相关单位」, 匹配存量 company)
_INTENT_ORG_SUFFIXES = (
    "有限公司", "有限责任公司", "股份有限公司", "公司", "研究院", "设计院", "勘察院",
    "工程局", "集团", "医院", "学校", "大学", "中心", "研究所", "事务所", "分公司",
    "管理处", "管理局", "水利局", "自然资源局", "镇政府", "乡政府", "街道办事处", "委员会",
)
# 姓名正则(用于从原文提取「XX负责/联系人」等, 匹配存量 person)
_INTENT_PERSON_RE = re.compile(r"([\u4e00-\u9fa5]{2,4})(?:先生|女士|同志)?(?:负责|联系人|联系|经办|电话|联系电话)")


def _extract_org_names(text: str) -> list:
    """从标题/原文提取可能的单位名片段(去重保序, 上限 20)。
    包含: 1) 后缀正则匹配; 2) 括号/书名号包住的机构名(常出现在公告标题)。"""
    if not text:
        return []
    names = []
    # 1) 后缀正则: 取后缀前的一串中文(2~30 字)作为候选单位名
    for suffix in _INTENT_ORG_SUFFIXES:
        for m in re.finditer(r"([\u4e00-\u9fa5]{2,30})" + suffix, text):
            cand = m.group(0).strip()
            if cand and cand not in names:
                names.append(cand)
            if len(names) >= 20:
                return names
    # 2) 括号/书名号包住的机构名: 形如「(四川省...)」「《...》」
    for m in re.finditer(r"[「《(](\S{4,40}?(?:厅|局|委|部|公司|院|中心|厂|集团))[\)」》]", text):
        cand = m.group(1).strip()
        if cand and cand not in names:
            names.append(cand)
    return names[:20]


def _fuzzy_match_company(cand: str, comp_by_name: dict) -> Company | None:
    """单位名模糊匹配: 全名 → 包含匹配 → 关键词重叠(去掉通用词后比对)。"""
    cand = cand.strip()
    if not cand:
        return None
    if cand in comp_by_name:
        return comp_by_name[cand]
    # 包含匹配
    for cname, cc in comp_by_name.items():
        if not cname:
            continue
        if cand in cname or (len(cand) >= 4 and cname in cand):
            return cc
    # 关键词重叠: 拆分候选与存量名, 去除通用词后比对核心词
    stop = {"省", "市", "县", "区", "公司", "有限责任", "集团", "股份", "有限", "中国", "四川"}
    cand_core = "".join(c for c in cand if c not in stop)[:8]
    if len(cand_core) < 4:
        return None
    for cname, cc in comp_by_name.items():
        if not cname or len(cname) < 4:
            continue
        cname_core = "".join(c for c in cname if c not in stop)[:8]
        if cand_core and cand_core == cname_core:
            return cc
    return None


def build_intent_relations(db: Session, intent_id: Optional[int] = None,
                           limit: Optional[int] = None) -> dict:
    """为意向批量建立真实关联实体(单位/人员), 写入 tender_match + Neo4j 图谱。

    数据来源(确定性, 非 LLM 拍脑袋):
      1) 意向标题/原文中的单位名(按后缀正则提取) → 匹配存量 company(全名/包含匹配)
      2) 意向标题/原文中的「XXX负责/联系人」人名 → 匹配存量 person(全名/包含匹配)
    这些实体即意向详情页「涉及单位/角色」「关联实体」的兜底真实数据,
    使未跑 AI 研判的意向也能展示真实关联单位。

    幂等: 已关联的跳过。intent_id 给定时只处理该意向, 否则处理全部非删除意向。
    返回 {"linked_companies", "linked_persons", "skipped", "failed"}
    """
    from app.models.intent_notice import IntentNotice
    if intent_id is not None:
        it = db.get(IntentNotice, intent_id)
        intents = [it] if it and not it.is_deleted else []
    else:
        q = select(IntentNotice).where(IntentNotice.is_deleted == False)
        if limit:
            q = q.limit(limit)
        intents = db.execute(q).scalars().all()

    # 存量索引
    companies = db.execute(
        select(Company).where(Company.is_deleted == False)
    ).scalars().all()
    persons = db.execute(
        select(Person).where(Person.is_deleted == False)
    ).scalars().all()
    comp_by_name = {}
    for c in companies:
        comp_by_name.setdefault((c.name or "").strip(), c)
    person_by_name = {}
    for p in persons:
        person_by_name.setdefault((p.name or "").strip(), p)

    linked_c = linked_p = skipped = failed = 0
    for it in intents:
        title = it.title or ""
        raw = (it.raw_text or "") or ""
        text = title + "\n" + raw
        if not text.strip():
            skipped += 1
            continue
        # 已有 intent_id 关联(避免重复)
        existing = {
            (m.entity_type, m.entity_id)
            for m in db.execute(
                select(TenderMatch).where(
                    TenderMatch.intent_id == it.id, TenderMatch.is_deleted == False
                )
            ).scalars().all()
        }
        valid_until = (it.published_at or datetime.now()) + timedelta(days=90)
        region = it.region or ""
        amount = str(int(it.amount)) if it.amount is not None else ""
        # 候选单位名: 正文提取 + 发布部门(dept, 政务公告常为政府机构)
        candidates = _extract_org_names(text)
        if it.dept and it.dept.strip():
            candidates.insert(0, it.dept.strip())
        seen_cands = set()
        try:
            # 1) 单位: 模糊匹配(全名/包含/核心词重叠) → 存量 company
            for cand in candidates:
                if cand in seen_cands:
                    continue
                seen_cands.add(cand)
                c = _fuzzy_match_company(cand, comp_by_name)
                if c is None:
                    continue
                key = ("company", c.id)
                if key in existing:
                    continue
                existing.add(key)
                _upsert_tender_match(
                    db, clue_id=None, intent_id=it.id, title=title,
                    entity_type="company", entity_id=c.id, entity_name=c.name or "",
                    match_type="owner", match_reason="标题/原文/发布部门模糊匹配业主单位",
                    score=0.85, region=region, amount=amount, valid_until=valid_until,
                )
                linked_c += 1
            # 2) 人员: 「XXX负责/联系人」人名 → 存量全名匹配
            for m in _INTENT_PERSON_RE.finditer(text):
                pname = m.group(1).strip()
                p = person_by_name.get(pname)
                if p is None:
                    continue
                key = ("person", p.id)
                if key in existing:
                    continue
                existing.add(key)
                _upsert_tender_match(
                    db, clue_id=None, intent_id=it.id, title=title,
                    entity_type="person", entity_id=p.id, entity_name=p.name or "",
                    match_type="contact", match_reason="标题/原文提取联系人",
                    score=0.8, region=region, amount=amount, valid_until=valid_until,
                )
                linked_p += 1
        except Exception:  # noqa: BLE001
            db.rollback()
            failed += 1
        db.commit()
    return {"linked_companies": linked_c, "linked_persons": linked_p,
            "skipped": skipped, "failed": failed, "intents": len(intents)}
