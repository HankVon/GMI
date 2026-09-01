"""中标活跃单位挖掘 — 从海量招标中标公告中聚合出「经常中标/拿到项目」的单位(常客榜)。

数据源: bid_notice.meta.suppliers 结构化供应商数组(爬虫已从公告详情页解析)。
挖掘维度:
  - 中标次数 / 累计金额 / 平均单次金额
  - 首次与最近中标时间 / 活跃月份数
  - 覆盖采购人(业主)与区域
  - 中标方向行业标签(命中行业关键词)
关联: 按归一化名称匹配 company 表, 补全单位画像(省份/城市/行业/统一信用代码)。

数据量小(千级), 采用全量实时聚合, 无需物化表; 后续量级上来可加缓存。
"""
import re
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

# ── 名称归一化 ──────────────────────────────────────────────
# 全角 → 半角(仅数字/括号, 单位名里的中文不动)
_FULLWIDTH = str.maketrans(
    "０１２３４５６７８９（）：",
    "0123456789():",
)
# 去掉结尾包号后缀: (包一) (标段2) (第1包) （包三） 等
_SUFFIX_RE = re.compile(
    r"[（(]\s*(?:第\s*)?(?:包|标段|段)?\s*[一二三四五六七八九十0-9]+\s*(?:包|标段|段)?\s*[）)]\s*$"
)
# 去掉「中标供应商:」「成交供应商:」「中标人:」等前缀
_PREFIX_RE = re.compile(r"^(?:中标|成交|中标成交|成交供应商|中标供应商|供应商|中标人|承包人)[：:、]?\s*")
_WS_RE = re.compile(r"\s+")


def normalize_name(name) -> str:
    """供应商名称归一化: 全角转半角 + 去包号后缀 + 去前缀/空白/孤立括号。
    保证「XX公司(包一)」「XX公司)」「XX公司 」等写法聚合为同一家。
    """
    if not name:
        return ""
    s = str(name).strip().translate(_FULLWIDTH)
    s = _PREFIX_RE.sub("", s)
    s = _SUFFIX_RE.sub("", s)
    s = _WS_RE.sub("", s)
    # 源数据常有残缺右括号残留(爬虫解析遗留), 去掉孤立括号
    s = s.rstrip(")）")
    s = s.rstrip("(（")
    return s.strip()


# ── 单位匹配 ───────────────────────────────────────────────
def _company_index(db: Session) -> dict:
    """构建 归一化名称 → Company 索引(含原名/简称两套)。"""
    from app.models.company import Company
    idx: dict = {}
    for c in db.execute(select(Company).where(Company.is_deleted == False)).scalars().all():
        for raw in (c.name, c.short_name):
            key = normalize_name(raw)
            if key and key not in idx:
                idx[key] = c
    return idx


# ── 主挖掘 ─────────────────────────────────────────────────
def mine_winners(
    db: Session,
    days: int = 0,
    min_count: int = 1,
    keyword: str = "",
    region: str = "",
    sort: str = "count",
    limit: int = 50,
) -> dict:
    """聚合中标公告里的供应商 → 高频中标单位榜单。

    参数:
      days: 时间窗(近N天, 0=全部)
      min_count: 最少中标次数(≥1 即全量, 推荐 2 只看常客)
      keyword: 单位名关键字过滤
      region: 区域关键字过滤(省/市)
      sort: count(次数)/amount(金额)/last(最近中标)
      limit: 返回条数
    """
    from app.models.bid_notice import BidNotice

    cutoff = datetime.now() - timedelta(days=days) if days else None

    agg: dict = {}  # norm_name → 统计
    bid_total = 0
    missing_time = 0

    for b in db.execute(
        select(BidNotice).where(BidNotice.is_deleted == False)
    ).scalars().all():
        # 时间窗只剔除「明确早于窗口」的记录; 发布时间缺失的公告仍计入
        # (采集现状: 大量中标公告未解析出 published_at, 直接丢弃会毁掉榜单)
        if cutoff and b.published_at and b.published_at < cutoff:
            continue
        bid_total += 1
        if not b.published_at:
            missing_time += 1
        suppliers = (b.meta or {}).get("suppliers") or [] if isinstance(b.meta, dict) else []
        for s in suppliers:
            if not isinstance(s, dict):
                continue
            raw = s.get("supplier") or s.get("name") or ""
            key = normalize_name(raw)
            if not key:
                continue
            rec = agg.setdefault(key, {
                "name": key,
                "win_count": 0,
                "total_amount": 0.0,
                "amounts": [],
                "win_dates": [],
                "purchasers": set(),
                "regions": set(),
                "bid_ids": set(),
                "titles": [],
            })
            rec["win_count"] += 1
            amt = s.get("amount")
            try:
                amt_f = float(amt) if amt is not None and str(amt).strip() else 0.0
            except (TypeError, ValueError):
                amt_f = 0.0
            # 金额统一按「元」入库, 展示转万元; 明显异常值(个位数/负数)忽略
            if amt_f > 100:
                rec["total_amount"] += amt_f
                rec["amounts"].append(amt_f)
            rec["win_dates"].append(b.published_at)
            if b.purchaser:
                rec["purchasers"].add(b.purchaser.strip())
            if b.region:
                rec["regions"].add(b.region.strip())
            rec["bid_ids"].add(b.id)
            if len(rec["titles"]) < 3 and b.title:
                rec["titles"].append(b.title.strip())

    if not agg:
        return _empty()

    # 关联 company 画像
    company_idx = _company_index(db)

    # 行业关键词 → 方向标签
    tags = _industry_tags(db)

    items = []
    for key, rec in agg.items():
        if rec["win_count"] < min_count:
            continue
        if keyword and keyword not in key and keyword not in rec["name"]:
            continue
        comp = company_idx.get(key)
        if comp:
            rec["company_id"] = comp.id
            rec["province"] = comp.province or ""
            rec["city"] = comp.city or ""
            rec["industry"] = comp.industry or ""
            rec["credit_code"] = comp.credit_code or ""
        win_dates = [d for d in rec["win_dates"] if d]
        last_win = max(win_dates) if win_dates else None
        first_win = min(win_dates) if win_dates else None
        # 活跃月份: 按 年-月 去重
        active_months = len({f"{d.year}-{d.month:02d}" for d in win_dates})

        rec["total_amount_wan"] = round(rec["total_amount"] / 10000, 2)
        rec["avg_amount_wan"] = round(rec["total_amount_wan"] / rec["win_count"], 2) if rec["win_count"] else 0
        rec["last_win"] = last_win.strftime("%Y-%m-%d") if last_win else ""
        rec["first_win"] = first_win.strftime("%Y-%m-%d") if first_win else ""
        rec["active_months"] = active_months
        rec["purchasers"] = sorted(rec["purchasers"])[:6]
        rec["regions"] = sorted(rec["regions"])[:6]
        rec["bid_ids"] = sorted(rec["bid_ids"])
        rec["tags"] = _match_tags(key, rec["name"], tags)
        items.append(rec)

    # 区域过滤
    if region:
        items = [it for it in items if any(region in r for r in it["regions"]) or region in (it.get("province") or "") or region in (it.get("city") or "")]

    # 排序
    sort_key = {"count": lambda x: x["win_count"], "amount": lambda x: x["total_amount"], "last": lambda x: x["last_win"]}.get(sort, lambda x: x["win_count"])
    items.sort(key=sort_key, reverse=True)
    items = items[:limit]

    # 整理输出字段
    out = []
    for it in items:
        out.append({
            "name": it["name"],
            "company_id": it.get("company_id"),
            "province": it.get("province", ""),
            "city": it.get("city", ""),
            "industry": it.get("industry", ""),
            "credit_code": it.get("credit_code", ""),
            "win_count": it["win_count"],
            "total_amount_wan": it["total_amount_wan"],
            "avg_amount_wan": it["avg_amount_wan"],
            "first_win": it["first_win"],
            "last_win": it["last_win"],
            "active_months": it["active_months"],
            "purchasers": it["purchasers"],
            "regions": it["regions"],
            "tags": it["tags"],
            "sample_titles": it["titles"],
        })

    total_amount = sum(it["total_amount"] for it in items)
    return {
        "success": True,
        "summary": {
            "bid_total": bid_total,
            "winner_total": len(items),
            "total_amount_wan": round(total_amount / 10000, 2),
            "sorted_by": sort,
            "missing_time": missing_time,
        },
        "items": out,
    }


def _industry_tags(db: Session) -> list:
    """行业关键词: 合并 GEO 配置词 + 默认词, 保证标签不依赖配置缺失。"""
    defaults = ["生态修复", "地质勘查", "地质灾害", "矿山治理", "水土保持", "勘察", "设计", "监理"]
    try:
        from app.services.geo_monitor import get_industry_keywords
        kws = get_industry_keywords(db) or []
    except Exception:  # noqa: BLE001
        kws = []
    seen: set = set()
    out = []
    for k in list(kws) + defaults:
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _match_tags(key: str, name: str, tags: list) -> list:
    pool = f"{key} {name}"
    return [t for t in tags if t and t in pool][:4]


def _empty() -> dict:
    return {"success": True, "summary": {
        "bid_total": 0, "winner_total": 0, "total_amount_wan": 0, "sorted_by": "count",
    }, "items": []}


# ── 反向关联: 中标单位 → 意向商机 ───────────────────────────

# 项目类别 → 意向业务词(用于「业务命中」证据)
_CATEGORY_BIZ_WORDS = {
    "geo_hazard": ["地质灾害", "地灾", "滑坡", "崩塌", "泥石流", "灾害", "治理"],
    "eco_restoration": ["生态修复", "生态", "环保", "环境治理", "矿山修复", "山水", "绿化"],
    "mining_rights": ["矿业权", "采矿", "探矿", "矿权", "矿产"],
    "geo_survey": ["勘察", "勘查", "测绘", "钻探", "地质", "岩土"],
    "policy": ["规划", "国土空间", "评估", "城市体检"],
}


def _winner_profile(db: Session, norm_key: str) -> dict:
    """构建中标单位的「做过项目」证据链画像。

    证据来源(真实项目参与关系, 而非仅公告文本):
      1. project_company: 该单位在库中参与/关联的项目(按公司名匹配)
      2. bid_notice → clue_id → web_clue.derived_project_id → Project: 该单位中标反推的项目
    从这些 Project 的 ext_attrs 提取 省/市/县 + 类别 + 项目名关键词。

    返回: {bid_count, provinces, cities, counties, categories, project_names, projects(证据明细)}
    """
    from app.models.bid_notice import BidNotice
    from app.models.web_clue import WebClue
    from app.models.project import Project
    from app.models.company import Company, ProjectCompany

    profile = {
        "bid_count": 0,
        "provinces": set(), "cities": set(), "counties": set(),
        "categories": set(), "project_names": set(),
        "projects": [],  # 证据明细: {project_id, name, province, city, county, category, source}
    }

    # 1) 找到公司 id(按归一化名/原名/简称)
    company_ids: set = set()
    for c in db.execute(select(Company).where(Company.is_deleted == False)).scalars().all():
        if any(normalize_name(r) == norm_key for r in (c.name, c.short_name)):
            company_ids.add(c.id)

    # 2) 从 project_company 参与关系取项目证据
    if company_ids:
        links = db.execute(
            select(ProjectCompany).where(
                ProjectCompany.company_id.in_(list(company_ids)),
                ProjectCompany.is_active == True,
            )
        ).scalars().all()
        for lk in links:
            proj = db.get(Project, lk.project_id)
            if proj and proj.is_deleted == False:
                ea = proj.ext_attrs if isinstance(proj.ext_attrs, dict) else {}
                profile["projects"].append({
                    "project_id": proj.id, "name": proj.name or "",
                    "province": ea.get("province") or "", "city": ea.get("city") or "",
                    "county": ea.get("county") or "", "category": ea.get("category") or "",
                    "source": "参与项目",
                })

    # 3) 从中标公告 → 线索 → 反推项目取项目证据
    for b in db.execute(
        select(BidNotice).where(BidNotice.is_deleted == False)
    ).scalars().all():
        suppliers = (b.meta or {}).get("suppliers") or [] if isinstance(b.meta, dict) else []
        hit = any(
            isinstance(s, dict) and normalize_name(s.get("supplier") or "") == norm_key
            for s in suppliers
        )
        if not hit:
            continue
        profile["bid_count"] += 1
        if b.clue_id:
            clue = db.get(WebClue, b.clue_id)
            if clue and clue.meta and isinstance(clue.meta, dict) and clue.meta.get("derived_project_id"):
                proj = db.get(Project, clue.meta["derived_project_id"])
                if proj and proj.is_deleted == False:
                    ea = proj.ext_attrs if isinstance(proj.ext_attrs, dict) else {}
                    profile["projects"].append({
                        "project_id": proj.id, "name": proj.name or "",
                        "province": ea.get("province") or "", "city": ea.get("city") or "",
                        "county": ea.get("county") or "", "category": ea.get("category") or "",
                        "source": "中标项目",
                    })

    # 4) 聚合画像(证据项目去重)
    seen_proj: set = set()
    for p in profile["projects"]:
        key = p["project_id"]
        if key in seen_proj:
            continue
        seen_proj.add(key)
        if p["province"]:
            profile["provinces"].add(p["province"])
        if p["city"]:
            profile["cities"].add(p["city"])
        if p["county"]:
            profile["counties"].add(p["county"])
        if p["category"]:
            profile["categories"].add(p["category"])
        profile["project_names"].add(p["name"])
    # 项目证据只保留前 8 条展示
    profile["projects"] = profile["projects"][:8]

    return profile


def mine_winner_opportunities(
    db: Session,
    name: str,
    days: int = 365,
    limit: int = 20,
) -> dict:
    """反向关联: 中标活跃单位 → 它可能关注的意向项目(强证据才推)。

    证据链原则(弱证据一律不推):
      - 先建立单位「做过什么项目」的证据(project_company 参与 + 中标反推 Project),
        每个证据含 地域(省/市/县) + 类别(category) + 项目名。
      - 意向项目须满足 双证据 才推荐:
          a. 地域命中: 意向的市/县 与 单位做过项目的地域 相同(同市/同县)
          b. 业务命中: 意向标题/行业 命中 单位做过项目的类别业务词 或 项目名核心词
        (仅同省、仅同地域、仅关键词 都视为弱证据, 一律不推)
    返回按 地域+业务 证据强度排序的意向列表, 每条附可解释证据。
    """
    from app.models.intent_notice import IntentNotice

    norm_key = normalize_name(name)
    if not norm_key:
        return {"success": True, "name": name, "items": []}

    profile = _winner_profile(db, norm_key)
    if not profile["projects"]:
        return {"success": True, "name": norm_key, "profile": _profile_out(profile), "items": [], "total": 0}

    # 单位证据: 地域(市县) + 类别业务词
    unit_cities = profile["cities"]
    unit_counties = profile["counties"]
    unit_cats = profile["categories"]
    # 地域词(用于剔除误当业务词的地域名)
    unit_geo_words: set = set(unit_cities) | set(unit_counties) | set(profile["provinces"])
    # 泛行政区词, 命中任何意向标题都会误配, 一律不作为业务证据
    _GENERIC_ADMIN_WORDS = {"高新", "经开", "新区", "园区", "高新东区", "高新区", "经开区"}
    # 业务词: 类别映射词 + 项目名核心词(剔除地域词 + 泛行政区词)
    unit_biz_words: set = set()
    for c in unit_cats:
        unit_biz_words.update(_CATEGORY_BIZ_WORDS.get(c, []))
    for n in profile["project_names"]:
        for seg in _split_name_keywords(n):
            if seg not in unit_geo_words and seg not in _GENERIC_ADMIN_WORDS:
                unit_biz_words.add(seg)

    cutoff = datetime.now() - timedelta(days=days) if days else None

    # 商机池 = ①省发改等政务源意向(intent_notice) ②招标/采购公告(web_clue 招标类, 含采购人/预算)
    scored = []
    # ① intent_notice
    intents = db.execute(
        select(IntentNotice).where(IntentNotice.is_deleted == False, IntentNotice.status != "expired")
    ).scalars().all()
    for it in intents:
        if cutoff and it.published_at and it.published_at < cutoff:
            continue
        region_txt = f"{it.region or ''} {it.province or ''} {it.city or ''} {it.county or ''}"
        title = f"{it.title or ''} {it.industry or ''}"
        hit = _match_opportunity(
            profile, unit_cities, unit_counties, unit_biz_words, region_txt, title
        )
        if not hit:
            continue
        scored.append({
            "intent_id": it.id,
            "kind": "intent",
            "title": it.title or "",
            "url": it.url or "",
            "project_type": it.project_type or "",
            "industry": it.industry or "",
            "region": it.region or (it.province or "") + (it.city or ""),
            "amount_wan": float(it.amount) if it.amount is not None else None,
            "published_at": it.published_at.strftime("%Y-%m-%d") if it.published_at else "",
            "dept": it.dept or "",
            "score": hit["score"],
            "reasons": hit["reasons"][:3],
        })

    # ② web_clue 招标/采购公告(排除中标结果类 source 7/8; 有采购人字段)
    from app.models.web_clue import WebClue
    from app.models.web_source import WebSource
    tender_sources = db.execute(
        select(WebSource).where(
            WebSource.scrape_mode == "query",
            WebSource.enabled == True,
            WebSource.is_deleted == False,
        )
    ).scalars().all()
    tender_src_ids = [w.id for w in tender_sources if "中标" not in (w.name or "")]
    clues = db.execute(
        select(WebClue).where(
            WebClue.is_deleted == False,
            WebClue.status == "accepted",
            WebClue.source_id.in_(tender_src_ids or [0]),
        )
    ).scalars().all()
    for c in clues:
        if cutoff and c.published_at and c.published_at < cutoff:
            continue
        title = c.title or ""
        # 排除中标/成交结果公告(已完成项目, 非当前商机)
        if any(k in title for k in ("中标（成交）结果公告", "中标结果公告", "成交公告", "中标候选人公示")):
            continue
        # 地域: 标题通常自带县市名(如「万源市自然资源局...」), 从中提取
        meta = c.meta if isinstance(c.meta, dict) else {}
        region_txt = f"{meta.get('region') or ''} {meta.get('regionName') or ''} {c.region or ''} {title}"
        budget = meta.get("budget")
        try:
            amount_wan = round(float(budget) / 10000, 2) if budget else None
        except (TypeError, ValueError):
            amount_wan = None
        hit = _match_opportunity(
            profile, unit_cities, unit_counties, unit_biz_words, region_txt, title
        )
        if not hit:
            continue
        purchasers = meta.get("purchaser")
        scored.append({
            "intent_id": c.id,
            "kind": "tender",
            "title": title,
            "url": c.url or "",
            "project_type": "",
            "industry": "",
            "region": (meta.get("regionName") or meta.get("region") or "")[:40],
            "amount_wan": amount_wan,
            "published_at": c.published_at.strftime("%Y-%m-%d") if c.published_at else "",
            "dept": (purchasers or "")[:80] if purchasers else "",
            "score": hit["score"],
            "reasons": hit["reasons"][:3],
        })

    scored.sort(key=lambda x: (-x["score"], x["published_at"] or ""))
    return {
        "success": True,
        "name": norm_key,
        "profile": _profile_out(profile),
        "items": scored[:limit],
        "total": len(scored),
    }


def _match_opportunity(
    profile: dict, unit_cities, unit_counties, unit_biz_words, region_txt: str, title: str
):
    """对单个商机做 双证据(地域+业务) 强匹配。

    返回 {score, reasons} 或 None(弱证据不推)。
    """
    # 证据1: 地域命中(同市/同县, 整词子串匹配)
    region_hit = ""
    for c in unit_cities:
        if c and len(c) >= 2 and c in region_txt:
            region_hit = c
            break
    if not region_hit:
        for ct in unit_counties:
            if ct and len(ct) >= 2 and ct in region_txt:
                region_hit = ct
                break
    if not region_hit:
        return None  # 地域不命中 → 不推(弱证据)

    # 证据2: 业务命中(类别业务词 或 项目名核心词 命中商机标题)
    biz_hits = [w for w in unit_biz_words if w and len(w) >= 2 and w in title]
    if not biz_hits:
        return None  # 仅地域命中而无业务证据 → 不推(弱证据)

    # 双证据成立: 给证据描述
    reasons = []
    # 找出支撑该地域命中的项目证据
    for p in profile["projects"]:
        if region_hit in (p["city"] or "") or region_hit in (p["county"] or ""):
            reasons.append(
                f"该单位在「{region_hit}」做过「{p['name'][:30]}」"
                f"({_CATEGORY_LABELS.get(p['category'], p['category'] or '未分类')}, {p['source']})"
            )
    reasons.append("商机同地域且标题命中业务词:" + "、".join(biz_hits[:3]))
    return {"score": 10 + len(biz_hits) * 2, "reasons": reasons}


# 类别中文标签(展示用)
_CATEGORY_LABELS = {
    "geo_hazard": "地质灾害", "eco_restoration": "生态修复", "mining_rights": "矿业权",
    "geo_survey": "勘察设计", "policy": "规划评估",
}


def _split_name_keywords(name: str) -> list:
    """从项目名提取核心业务词(≥2字中文片段, 去地域/行政区/通用词)。"""
    if not name:
        return []
    t = str(name)
    # 地域/行政区/通用后缀一律剔除(防止「高新区」「经开区」等泛词误命中无关意向)
    for drop in ("市", "州", "区", "县", "镇", "乡", "项目", "工程", "有限公司", "勘查设计", "勘察设计",
                 "高新区", "经开区", "新区", "园区", "2026", "2025"):
        t = t.replace(drop, " ")
    words = []
    for seg in re.split(r"[\s，。；：、,.（）()]+", t):
        seg = seg.strip()
        if 2 <= len(seg) <= 12 and not seg.isdigit():
            words.append(seg)
    return words[:6]


def _profile_out(p: dict) -> dict:
    return {
        "bid_count": p["bid_count"],
        "provinces": sorted(p["provinces"])[:5],
        "cities": sorted(p["cities"])[:5],
        "counties": sorted(p["counties"])[:5],
        "categories": sorted(p["categories"])[:5],
        "projects": p["projects"][:8],
    }
