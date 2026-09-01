"""机会侦察引擎 — 从项目库/人脉/中标推导"高价值目标单位 × 意向栏目 × 检索关键词"。

核心价值: 把"该盯谁、查什么"从人肉配置变成数据驱动推理, 直接喂给采集层执行。

推理输入(数据源):
  1. 近 180 天有 ≥2 条招标/中标的活跃采购人(BidNotice.purchaser / WebClue meta.purchaser)
  2. 业务关键词命中(地灾/生态/矿山/勘察等)的采购人 → 高优先级
  3. 项目库在跟项目已关联的采购人(ProjectClue.purchaser)
  4. 人脉图中与 person/company 相连的单位(NetworkEdge)

推理输出:
  [{unit, province, city, keywords[], sources[], reason, score, last_activity}]
  keywords 直接作为意向检索关键词(交 intent_crawler / query_crawl 执行)。

反哺闭环:
  - 采集结果写回 intent_notice(matched_entity 关联 company)
  - project_tracker.match_all_clues 把新意向关联到项目
  - 目标单位画像写回 company.ext_attrs.scout 供下一轮推理参考
"""
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.bid_notice import BidNotice
from app.models.web_clue import WebClue
from app.models.intent_notice import IntentNotice
from app.models.project_clue import ProjectClue
from app.models.company import Company
from app.services.china_regions import extract_target_province, resolve_region

logger = logging.getLogger("opportunity_scout")

# 业务关键词(与 intent_crawler._BUSINESS_KEYWORDS 对齐)
_BUSINESS_KW = [
    "地质灾害", "地灾", "滑坡", "泥石流", "崩塌", "地面塌陷", "隐患治理", "排危",
    "生态修复", "生态治理", "环境治理", "矿山修复", "矿山地质", "恢复治理",
    "水土保持", "水土流失", "小流域治理",
    "地质勘察", "地质勘查", "工程勘察", "岩土", "钻探", "监测预警", "地质环境监测", "测绘",
    "地灾评估", "危险性评估", "勘查设计", "勘察设计",
]
# 目标省份采购人类别词(识别政府单位)
_GOV_KW = ("自然资源", "规划", "住建", "发改委", "经信", "水利", "交通", "人民政府",
           "财政局", "农业农村", "生态环境", "应急", "人民政府采购中心", "公共资源")
# 默认意向检索关键词模板(按单位所在市/县 + 业务词)
_KEYWORD_TPL = [
    "{region}地质灾害", "{region}生态修复", "{region}矿山治理", "{region}水土保持",
    "{region}地质勘查", "{region}采购意向", "{region}招标预告",
]


def _agg_bid_purchasers(db: Session, days: int = 180) -> dict:
    """聚合近 days 天中标公告的采购人 → {purchaser: {count, category_hits, last_at, region}}。"""
    since = datetime.now() - timedelta(days=days)
    rows = db.execute(
        select(BidNotice).where(
            BidNotice.is_deleted == False,
            BidNotice.purchaser.isnot(None),
            BidNotice.published_at >= since,
        )
    ).scalars().all()
    agg: dict = defaultdict(lambda: {"count": 0, "category_hits": 0, "last_at": None, "region": ""})
    for b in rows:
        p = b.purchaser.strip()
        if not p:
            continue
        a = agg[p]
        a["count"] += 1
        if any(k in (b.title or "") for k in _BUSINESS_KW):
            a["category_hits"] += 1
        if not a["last_at"] or (b.published_at and b.published_at > a["last_at"]):
            a["last_at"] = b.published_at
        if not a["region"] and b.region:
            a["region"] = b.region
    return agg


def _agg_clue_purchasers(db: Session, days: int = 180) -> dict:
    """聚合招标/意向线索(web_clue + intent_notice)的采购人 → 同上。"""
    since = datetime.now() - timedelta(days=days)
    agg: dict = defaultdict(lambda: {"count": 0, "category_hits": 0, "last_at": None, "region": ""})
    # web_clue meta.purchaser
    clues = db.execute(
        select(WebClue).where(
            WebClue.is_deleted == False,
            WebClue.status == "accepted",
            WebClue.published_at >= since,
        )
    ).scalars().all()
    for c in clues:
        meta = c.meta if isinstance(c.meta, dict) else {}
        p = (meta.get("purchaser") or "").strip()
        if not p:
            continue
        a = agg[p]
        a["count"] += 1
        if any(k in (c.title or "") for k in _BUSINESS_KW):
            a["category_hits"] += 1
        if not a["last_at"] or (c.published_at and c.published_at > a["last_at"]):
            a["last_at"] = c.published_at
        if not a["region"] and c.region:
            a["region"] = c.region
    # intent_notice
    intents = db.execute(
        select(IntentNotice).where(
            IntentNotice.is_deleted == False,
            IntentNotice.published_at >= since,
        )
    ).scalars().all()
    for it in intents:
        # 发改委批复解析出的项目业主(matched_entity.unit)优先
        me = None
        if it.matched_entity:
            try:
                import json as _json
                me = _json.loads(it.matched_entity)
            except Exception:  # noqa: BLE001
                me = None
        p = ""
        if me and me.get("unit"):
            p = me["unit"]
        if not p and it.dept:
            p = it.dept
        if not p:
            continue
        a = agg[p]
        a["count"] += 1
        if any(k in (it.title or "") for k in _BUSINESS_KW):
            a["category_hits"] += 1
        if not a["last_at"] or (it.published_at and it.published_at > a["last_at"]):
            a["last_at"] = it.published_at
        if not a["region"] and it.region:
            a["region"] = it.region
    return agg


def _project_purchasers(db: Session) -> dict:
    """项目库在跟项目已关联的采购人(ProjectClue) → {purchaser: {count, region}}。"""
    rows = db.execute(
        select(ProjectClue).where(ProjectClue.is_deleted == False, ProjectClue.purchaser != "")
    ).scalars().all()
    agg: dict = defaultdict(lambda: {"count": 0, "region": ""})
    for r in rows:
        p = (r.purchaser or "").strip()
        if not p:
            continue
        agg[p]["count"] += 1
        if not agg[p]["region"] and r.region:
            agg[p]["region"] = r.region
    return agg


def _region_of(unit: str, fallback: str = "") -> dict:
    """从单位名或兜底地域解析 省/市/县。

    策略:
      1. 兜底地域(fallback, 来自公告 region)优先
      2. 单位名含市核心词(巴中/广元/阿坝等) → resolve_region(city=)
      3. 单位名含县核心词(汉源/苍溪/若尔盖等) → resolve_region(county=)
      4. extract_target_province 兜底省
    """
    if fallback:
        rg = resolve_region("", "", fallback)
        if rg.get("matched"):
            return rg
    from app.services.china_regions import city_core, county_core
    for cand in _city_county_words():
        if cand in unit:
            c = city_core(cand)
            if c:
                rg = resolve_region("", c, "")
                if rg.get("matched"):
                    return rg
            ct = county_core(cand)
            if ct:
                rg = resolve_region("", "", ct)
                if rg.get("matched"):
                    return rg
    prov = extract_target_province(unit)
    if prov:
        return {"province": prov, "city": "", "county": ""}
    return {"province": "", "city": "", "county": ""}


_city_county_cache: list = []


def _city_county_words() -> list:
    """目标省份(川藏新)全部市/县级词(缓存)。"""
    global _city_county_cache
    if not _city_county_cache:
        from app.services.china_regions import REGION_COUNTIES, _CITY_OF, TARGET_PROVINCES
        for city, prov in _CITY_OF.items():
            if prov in TARGET_PROVINCES:
                _city_county_cache.append(city)
                _city_county_cache.extend(REGION_COUNTIES.get(city, []))
        _city_county_cache = list(dict.fromkeys(_city_county_cache))
    return _city_county_cache


def _gen_keywords(region: str) -> list:
    """按目标单位地域生成意向检索关键词。"""
    if not region:
        return list(_BUSINESS_KW)
    return [t.format(region=region) for t in _KEYWORD_TPL] + list(_BUSINESS_KW)


def _score_unit(unit: str, agg: dict, srcs: set) -> float:
    """目标单位评分: 活跃度 + 业务重叠 + 政府属性 + 来源数。"""
    score = 0.0
    if agg.get("category_hits"):
        score += 4.0 + min(agg["category_hits"], 5)
    score += min(agg.get("count", 0), 10) * 0.5
    if any(k in unit for k in _GOV_KW):
        score += 2.0
    score += min(len(srcs), 3)
    return round(score, 1)


def scout_targets(db: Session, days: int = 180, top_n: int = 30) -> list:
    """推导高价值目标单位清单(按分数降序)。

    返回 [{unit, province, city, region_label, keywords[], sources[], reason,
          score, count, category_hits, last_activity}]
    """
    bid_agg = _agg_bid_purchasers(db, days)
    clue_agg = _agg_clue_purchasers(db, days)
    proj_agg = _project_purchasers(db)

    units: dict = {}
    for name, agg in bid_agg.items():
        units.setdefault(name, {"agg": agg, "sources": set()})["sources"].add("中标")
    for name, agg in clue_agg.items():
        units.setdefault(name, {"agg": agg, "sources": set()})["sources"].add("招标/意向")
    for name, agg in proj_agg.items():
        units.setdefault(name, {"agg": agg, "sources": set()})["sources"].add("在跟项目")

    out = []
    for name, item in units.items():
        agg = item["agg"]
        srcs = item["sources"]
        # 过滤: 无活跃度且非在跟项目 → 跳过(避免噪音)
        if agg.get("count", 0) < 1 and "在跟项目" not in srcs:
            continue
        score = _score_unit(name, agg, srcs)
        rg = _region_of(name, agg.get("region", ""))
        if not rg.get("province") and "在跟项目" not in srcs:
            # 无法确认地域的目标单位, 保留但降权(可能非目标省份)
            score -= 2.0
        region_label = "".join(filter(None, [
            rg.get("province_label"), rg.get("city_label"), rg.get("county_label")]))
        reasons = []
        if agg.get("category_hits"):
            reasons.append(f"近期{agg['category_hits']}条业务相关公告")
        reasons.append(f"{agg.get('count', 0)}条活跃记录")
        if "在跟项目" in srcs:
            reasons.append("项目在跟")
        out.append({
            "unit": name,
            "province": rg.get("province", ""),
            "city": rg.get("city", ""),
            "county": rg.get("county", ""),
            "region_label": region_label,
            "keywords": _gen_keywords(rg.get("city") or rg.get("county") or rg.get("province", "")),
            "sources": sorted(srcs),
            "reason": "、".join(reasons),
            "score": score,
            "count": agg.get("count", 0),
            "category_hits": agg.get("category_hits", 0),
            "last_activity": agg.get("last_at").strftime("%Y-%m-%d") if agg.get("last_at") else "",
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:top_n]


def feedback_to_companies(db: Session, targets: list, max_units: int = 30) -> dict:
    """反哺闭环: 把侦察出的高价值目标单位画像写回 company.ext_attrs.scout。

    ext_attrs.scout = {last_scout_at, score, count, category_hits, sources,
                       reason, keywords, followed_since}
    供下一轮推理参考(已盯很久仍无收获的降权/未匹配公司的补建)。
    返回 {"updated": n, "matched_companies": n}
    """
    from app.models.company import Company
    updated = 0
    matched_companies = 0
    now = datetime.now()
    for t in targets[:max_units]:
        unit = t["unit"]
        # 在 company 库找(名称包含/相等)
        c = None
        for cand in db.execute(
            select(Company).where(
                Company.is_deleted == False,
                Company.name.contains(unit[:8]),
            ).limit(5)
        ).scalars().all():
            if unit in cand.name or cand.name in unit:
                c = cand
                break
        if not c:
            continue
        ext = dict(c.ext_attrs or {})
        prev_scout = ext.get("scout") or {}
        ext["scout"] = {
            "last_scout_at": now.strftime("%Y-%m-%d %H:%M"),
            "score": t["score"],
            "count": t.get("count", 0),
            "category_hits": t.get("category_hits", 0),
            "sources": t.get("sources", []),
            "reason": t.get("reason", ""),
            "keywords": t.get("keywords", [])[:10],
            "followed_since": prev_scout.get("followed_since") or now.strftime("%Y-%m-%d"),
            "rounds": int(prev_scout.get("rounds") or 0) + 1,
        }
        c.ext_attrs = ext
        updated += 1
        if c.id:
            matched_companies += 1
    db.commit()
    return {"updated": updated, "matched_companies": matched_companies}


def scout_summary(db: Session, days: int = 180) -> dict:
    """侦察摘要(供看板/调度日志): 目标数 + 高优先 + 各来源分布。"""
    targets = scout_targets(db, days=days, top_n=100)
    high = [t for t in targets if t["score"] >= 6.0]
    return {
        "total_targets": len(targets),
        "high_priority": len(high),
        "business_hit": sum(1 for t in targets if t["category_hits"]),
        "top_targets": targets[:10],
        "source_distribution": dict(Counter(s for t in targets for s in t["sources"])),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
