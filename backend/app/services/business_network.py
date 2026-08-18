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
    """把招标/意向线索(web_clue)与人员/单位匹配推荐。

    匹配逻辑(加权):
      - 专长匹配: 线索标题含人员专长(skill) → 人员 高优先级
      - 类别匹配: 线索标题含 项目类别关键词 → 相关人员/单位
      - 区域匹配: 线索地域与单位省份/城市一致
      - 单位匹配: 线索关键词命中单位业务关键词(company_type/行业)
    写入 tender_match 表(幂等: 同 clue+entity 更新)。
    """
    from app.models.web_clue import WebClue

    # 候选线索: 意向/招标类
    intent_kw = ("采购意向", "意向公开", "采购需求", "招标", "采购公告", "中标", "勘察", "地质灾害", "生态修复")
    stmt = select(WebClue).where(
        WebClue.is_deleted == False,
        WebClue.title != None,
    ).order_by(WebClue.id.desc()).limit(300)
    if clue_id:
        stmt = stmt.where(WebClue.id == clue_id)
    clues = db.execute(stmt).scalars().all()

    persons = db.execute(select(Person).where(Person.is_deleted == False)).scalars().all()
    companies = db.execute(select(Company).where(Company.is_deleted == False)).scalars().all()
    person_skills = {}
    for ps in db.execute(select(PersonSkill).where(PersonSkill.is_deleted == False)).scalars().all():
        person_skills.setdefault(ps.person_id, []).append(ps.skill)

    matched = 0
    now = datetime.now()
    for clue in clues:
        title = clue.title or ""
        if not any(k in title for k in intent_kw):
            continue
        meta = clue.meta if isinstance(clue.meta, dict) else {}
        region = meta.get("regionName") or clue.region or ""
        amount = str(meta.get("budget") or "")
        # 推荐有效期: 优先线索截止时间(expireTime), 否则发布时间+60天, 再否则抓取时间+60天
        valid_until = _compute_valid_until(meta, clue.published_at or clue.fetched_at or now)
        best_person, best_company = None, None
        best_p_score, best_c_score = 0.0, 0.0

        # 人员: 专长命中
        for p in persons:
            skills = person_skills.get(p.id, [])
            score = 0.0
            reason = []
            for s in skills:
                if s and s in title:
                    score += 0.6
                    reason.append(f"专长「{s}」")
            # 单位区域匹配加分
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
            _upsert_tender_match(db, clue.id, title, "person", best_person.id,
                                 best_person.name or "", "skill", f"专长匹配(得分{best_p_score:.2f})",
                                 best_p_score, region, amount, valid_until)
            matched += 1
        if best_company and best_c_score >= 0.6:
            _upsert_tender_match(db, clue.id, title, "company", best_company.id,
                                 best_company.name or "", "category", f"业务匹配(得分{best_c_score:.2f})",
                                 best_c_score, region, amount, valid_until)
            matched += 1

    db.commit()
    return {"matched": matched, "candidates": len(clues)}


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


def _upsert_tender_match(db, clue_id, title, etype, eid, ename, mtype, reason, score, region, amount,
                         valid_until=None):
    """幂等写 tender_match。"""
    exists = db.execute(
        select(TenderMatch).where(
            TenderMatch.clue_id == clue_id,
            TenderMatch.entity_type == etype, TenderMatch.entity_id == eid,
            TenderMatch.is_deleted == False,
        ).limit(1)
    ).scalar_one_or_none()
    if exists:
        exists.score = score
        exists.match_reason = reason
        if valid_until:
            exists.valid_until = valid_until
    else:
        db.add(TenderMatch(
            clue_id=clue_id, title=title[:500], entity_type=etype, entity_id=eid,
            entity_name=ename, match_type=mtype, match_reason=reason,
            score=score, region=region or None, amount=amount or None, status="new",
            valid_until=valid_until,
        ))
    db.flush()
