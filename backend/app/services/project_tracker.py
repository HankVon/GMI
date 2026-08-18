"""项目跟踪器 — 把意向/招标/中标/施工线索增量归整到对应项目, 支持自动监控各阶段。

设计(防张冠李戴的核心):
  1. 复用 project_context 的强相关匹配: 市级/县级地域命中 或 类别词/项目核心词命中 才算关联;
     仅省级命中(四川)不算。
  2. 类别一致性硬约束: 线索标题可识别类别(生态/地灾/矿业/勘察/规划)时, 必须与项目类别一致,
     否则即使地域命中也不关联(例: 生态修复线索不会挂到地质勘察项目)。
  3. 每条线索只关联 1 个项目(取置信度最高), 避免同一线索被多个项目收录。
  4. 持久化到 project_clue, 幂等(唯一键), 项目详情按阶段分组展示完整跟踪时间线。

触发: 数据流水线 filter 之后 + 每日定时增量 + 手动 POST /projects/tracker/run。
"""
import logging
import re
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.web_clue import WebClue
from app.models.bid_notice import BidNotice
from app.models.intent_notice import IntentNotice
from app.models.project_clue import ProjectClue
from app.services.china_regions import extract_target_province

logger = logging.getLogger("project_tracker")

# 阶段特征词
_INTENT_KW = ("采购意向", "意向公开", "采购需求", "需求公示", "预公告", "采购计划", "意向")
_BIDDING_KW = ("招标", "采购公告", "磋商", "竞争性", "询价", "比选", "谈判", "单一来源", "竞价")
_AWARD_KW = ("中标", "成交")
_CONSTRUCT_KW = ("施工总承包", "主体施工", "开工", "进场施工", "施工合同")

# 类别识别词(与 project_category 枚举对齐)
_CATEGORY_WORDS = {
    "eco_restoration": ("生态修复", "生态保护", "环境治理", "生态功能区", "水源涵养", "水污染", "绿化", "植被"),
    "geo_hazard": ("地质灾害", "地灾", "滑坡", "崩塌", "泥石流", "防治", "排危", "群测"),
    "mining_rights": ("矿业", "采矿", "矿权", "探矿", "储量", "矿产"),
    "geo_survey": ("勘察", "勘查", "测绘", "岩土", "钻探", "详查", "地质"),
    # 只含业务组合词(与 project_context 对齐): 不含孤立「规划/政策/编制」
    # (机构名「自然资源和规划局」每条公告都有「规划」, 会误配; 「政策解读」会误配规划项目)
    "policy": ("专项规划", "总体规划", "国土空间", "规划编制", "城市体检", "评估咨询", "发展规划"),
}


def _derive_stage(title: str) -> str:
    t = title or ""
    if any(k in t for k in _INTENT_KW):
        return "investment"
    if any(k in t for k in _AWARD_KW):
        return "awarded"
    if any(k in t for k in _CONSTRUCT_KW):
        return "construction"
    if any(k in t for k in _BIDDING_KW):
        return "bidding"
    return "bidding"


def _clue_category(title: str) -> str:
    """从线索标题识别类别; 识别不出返回空(不施加类别硬约束)。"""
    t = title or ""
    for cat, words in _CATEGORY_WORDS.items():
        if any(w in t for w in words):
            return cat
    return ""


def _clue_region_fields(text: str) -> dict:
    """从线索文本提取省/市/县(与 project_context._extract_region_from_text 对齐)。"""
    from app.services.china_regions import REGION_COUNTIES, _CITY_OF, TARGET_PROVINCES
    if not text:
        return {"province": "", "city": "", "county": ""}
    prov = extract_target_province(text)
    county = ""
    for city_key, counties in REGION_COUNTIES.items():
        if _CITY_OF.get(city_key) not in TARGET_PROVINCES:
            continue
        for ct in counties:
            if ct and ct in text:
                county = ct
                break
        if county:
            break
    city = ""
    for c, p in _CITY_OF.items():
        if p in TARGET_PROVINCES and c in text:
            city = c
            break
    return {"province": prov, "city": city, "county": county}


def _project_ctx(project: Project) -> dict:
    """项目上下文(与 project_context._project_ctx 对齐, 避免跨层依赖)。"""
    ext = project.ext_attrs or {}
    name = str(project.name or "")
    province = (ext.get("province") or "").strip()
    city = (ext.get("city") or "").strip()
    county = (ext.get("county") or "").strip()
    from_name = _clue_region_fields(name)
    province = province or from_name["province"]
    city = city or from_name["city"]
    county = county or from_name["county"]
    category = (ext.get("category") or "").strip()
    name_kw = name.replace("项目", "").replace("工程", "").strip()[:6]
    return {"province": province, "city": city, "county": county,
            "category": category, "name_kw": name_kw}


def _region_overlap(p1, c1, k1, p2, c2, k2, text2: str) -> tuple:
    """市级/县级强地域匹配(与 project_context._zh_region_overlap 一致)。"""
    score, strong = 0, False
    # ≥2字中文词用子串匹配(词前必是中文, 负向前瞻会让真实命中全失败)
    if c1:
        if c2 == c1 or (len(c1) >= 2 and c1 in (text2 or "")):
            score += 2
            strong = True
    if k1:
        if k2 == k1 or (len(k1) >= 2 and k1 in (text2 or "")):
            score += 2
            strong = True
    return score, strong


def _keyword_overlap(kw: str, text: str, category: str = "") -> tuple:
    """类别词/项目核心词子串命中(与 project_context._keyword_overlap 一致)。"""
    score, strong = 0, False
    if not kw and not category:
        return 0, False
    cat_map = {
        "geo_hazard": ["地质灾害", "地灾", "滑坡", "崩塌", "泥石流", "防治", "排危"],
        "eco_restoration": ["生态修复", "生态保护", "环境治理", "综合治理", "生态功能区", "水源涵养"],
        "mining_rights": ["矿业", "采矿", "矿权", "探矿", "矿产", "储量"],
        "geo_survey": ["勘察", "勘查", "测绘", "地质", "岩土", "详查", "监测", "钻探"],
        # 只含业务组合词——孤立「规划」会因机构名「自然资源和规划局」误配; 「政策」会误配政策解读
        "policy": ["专项规划", "总体规划", "国土空间", "规划编制", "城市体检", "评估咨询", "发展规划"],
    }
    if category:
        for cat, words in cat_map.items():
            if category == cat:
                if any(w in (text or "") for w in words):
                    score += 2
                    strong = True
                break
    if kw:
        for t in _extract_key_tokens(kw):
            if len(t) >= 2 and t in (text or ""):
                score += 2
                strong = True
    return score, strong


def _extract_key_tokens(name: str) -> list:
    for drop in ("成都市", "绵阳市", "广元市", "自贡市", "达州市", "广安市", "雅安市",
                 "自治区", "自治州", "地区", "市", "省", "县", "区",
                 "有限公司", "有限责任公司", "政府采购", "项目", "工程", "建设"):
        name = name.replace(drop, "")
    return re.findall(r"[\u4e00-\u9fa5]{2,}", name)[:3]


def _match_to_project(clue_title: str, clue_text: str, clue_reg: dict,
                      purchaser: str, projects: list) -> tuple:
    """把一条线索与所有项目匹配, 返回 (project_id, confidence, reason) 或 None。

    防张冠李戴三要素:
      1. 强相关门槛: 市/县地域命中 或 类别词/核心词命中
      2. 类别硬约束: 线索可识别类别时, 必须与项目类别一致
      3. 每线索只取 1 个最佳项目
    """
    clue_cat = _clue_category(clue_title)
    best: tuple = None
    for p in projects:
        ctx = _project_ctx(p)
        r_score, r_strong = _region_overlap(ctx["province"], ctx["city"], ctx["county"],
                                            clue_reg.get("province", ""), clue_reg.get("city", ""),
                                            clue_reg.get("county", ""), clue_text)
        k_score, k_strong = _keyword_overlap(ctx["name_kw"], clue_text, ctx["category"])
        if not (r_strong or k_strong):
            continue
        # 类别硬约束: 线索类别已知且与项目类别不同 → 拒绝(即使地域命中)
        if clue_cat and ctx["category"] and clue_cat != ctx["category"]:
            continue
        score = r_score + k_score
        # 单位一致性加分: 线索采购人与项目单位名匹配
        unit_hit = False
        if purchaser and ctx.get("name_kw") and purchaser == ctx["name_kw"]:
            unit_hit = True
            score += 2
        # 防张冠李戴门槛: 仅市级命中(score=2)或仅类别词命中(score=2)不足以关联
        # (修复前: 成都范围内任何线索都会挂到成都项目, 如「电子病历维护/特高压」误配「安居房勘察」)
        # 要求: 县级命中(4) 或 市级+主题(4) 或 类别+核心词(4) 或 市级+单位一致(4) 等双信号
        if score < 4:
            continue
        reason_parts = []
        if r_strong:
            reason_parts.append("地域强匹配(市/县)")
        if k_strong:
            reason_parts.append(f"主题匹配({ctx['category'] or '核心词'})")
        if unit_hit:
            reason_parts.append("单位一致")
        confidence = round(min(0.99, 0.55 + 0.10 * score), 2)
        if best is None or score > best[0]:
            best = (score, confidence, p.id, "、".join(reason_parts) or "相关线索")
    if best is None:
        return None
    _s, conf, pid, reason = best
    if conf < 0.6:
        return None
    return (pid, conf, reason)


def _existing_keys(db: Session) -> set:
    rows = db.execute(
        select(ProjectClue.clue_type, ProjectClue.clue_id).where(ProjectClue.is_deleted == False)
    ).all()
    return {(r[0], r[1]) for r in rows}


def match_all_clues(db: Session, limit: int = 3000) -> dict:
    """增量把未关联的 意向/招标线索/中标公告 归整到项目。幂等。

    返回 {"intent": n, "web_clue": n, "bid": n, "total": n, "projects": n}
    """
    projects = list(db.execute(
        select(Project).where(Project.is_deleted == False)
    ).scalars().all())
    if not projects:
        return {"intent": 0, "web_clue": 0, "bid": 0, "total": 0, "projects": 0}
    existing = _existing_keys(db)
    stats = {"intent": 0, "web_clue": 0, "bid": 0}

    # 1) 意向公告
    intents = db.execute(
        select(IntentNotice).where(IntentNotice.is_deleted == False)
        .order_by(IntentNotice.published_at.desc()).limit(limit)
    ).scalars().all()
    for it in intents:
        if ("intent", it.id) in existing:
            continue
        title = it.title or ""
        text = " ".join([title, it.region or "", it.dept or ""])
        reg = {"province": it.province or "", "city": it.city or "", "county": it.county or ""}
        m = _match_to_project(title, text, reg, "", projects)
        if m:
            pid, conf, reason = m
            db.add(ProjectClue(project_id=pid, clue_type="intent", clue_id=it.id,
                               stage=_derive_stage(title), title=title, url=it.url or "",
                               source_name=it.dept or "政务源", region=it.region or "",
                               purchaser=it.dept or "", published_at=it.published_at,
                               fetched_at=it.published_at, confidence=conf, match_reason=reason))
            stats["intent"] += 1

    # 2) 网页线索(招标期/中标期)
    clues = db.execute(
        select(WebClue).where(WebClue.is_deleted == False, WebClue.status == "accepted")
        .order_by(WebClue.published_at.desc()).limit(limit)
    ).scalars().all()
    for c in clues:
        if ("web_clue", c.id) in existing:
            continue
        meta = c.meta if isinstance(c.meta, dict) else {}
        title = c.title or ""
        text = " ".join([title, c.region or "", meta.get("regionName") or "",
                         meta.get("regionName_") or "", meta.get("purchaserAddr") or "",
                         meta.get("purchaser") or ""])
        reg = _clue_region_fields(text)
        if not reg.get("province"):
            continue
        m = _match_to_project(title, text, reg, meta.get("purchaser") or "", projects)
        if m:
            pid, conf, reason = m
            db.add(ProjectClue(project_id=pid, clue_type="web_clue", clue_id=c.id,
                               stage=_derive_stage(title), title=title, url=c.url or "",
                               source_name=c.source_name or "网页线索", region=c.region or "",
                               purchaser=meta.get("purchaser") or "", published_at=c.published_at,
                               fetched_at=c.fetched_at, confidence=conf, match_reason=reason))
            stats["web_clue"] += 1

    # 3) 中标公告
    bids = db.execute(
        select(BidNotice).where(BidNotice.is_deleted == False)
        .order_by(BidNotice.published_at.desc()).limit(limit)
    ).scalars().all()
    for bn in bids:
        if ("bid", bn.id) in existing:
            continue
        title = bn.title or ""
        text = " ".join([title, bn.purchaser or "", bn.region or ""])
        reg = _clue_region_fields(text)
        if not reg.get("province"):
            continue
        m = _match_to_project(title, text, reg, bn.purchaser or "", projects)
        if m:
            pid, conf, reason = m
            db.add(ProjectClue(project_id=pid, clue_type="bid", clue_id=bn.id,
                               stage=_derive_stage(title), title=title, url=bn.url or "",
                               source_name=bn.source_name or "中标公告", region=bn.region or "",
                               purchaser=bn.purchaser or "", published_at=bn.published_at,
                               fetched_at=bn.fetched_at, confidence=conf, match_reason=reason))
            stats["bid"] += 1

    db.commit()
    stats["total"] = sum(stats.values())
    stats["projects"] = len(projects)
    return stats


def tracked_clues(db: Session, project_id: int) -> list:
    """项目已跟踪线索(按阶段分组+时间倒序)。"""
    rows = db.execute(
        select(ProjectClue).where(ProjectClue.project_id == project_id,
                                  ProjectClue.is_deleted == False)
        .order_by(ProjectClue.published_at.desc())
    ).scalars().all()
    groups = {"investment": [], "bidding": [], "awarded": [], "construction": []}
    for r in rows:
        d = {
            "id": r.id, "clue_type": r.clue_type, "clue_id": r.clue_id,
            "stage": r.stage, "title": r.title or "", "url": r.url or "",
            "source_name": r.source_name or "", "region": r.region or "",
            "purchaser": r.purchaser or "",
            "published_at": r.published_at.strftime("%Y-%m-%d") if r.published_at else "",
            "confidence": float(r.confidence or 0), "match_reason": r.match_reason or "",
            "is_read": bool(r.is_read),
        }
        groups.setdefault(r.stage, []).append(d)
    out = []
    stage_order = ["investment", "bidding", "awarded", "construction"]
    stage_zh = {"investment": "投资意向期", "bidding": "招标期", "awarded": "中标公示期", "construction": "施工期"}
    for s in stage_order:
        if groups.get(s):
            out.append({"stage": s, "stage_label": stage_zh[s], "items": groups[s]})
    return out


def mark_read(db: Session, clue_id: int) -> None:
    r = db.get(ProjectClue, clue_id)
    if r:
        r.is_read = True
        db.commit()
