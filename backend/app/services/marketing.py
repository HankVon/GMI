"""营销智能体决策层 — 商机评分 / 内容选题推荐 / 闭环看板。

把「感知(GEO监测+情报采集) → 决策(商机评分+选题) → 执行(内容工厂) →
反馈(GEO引用回流)」串成一条可运营的营销闭环。
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger("marketing")

# 行业关键词与地域(默认值, 可被 mk_config 覆盖)
_DEFAULT_INDUSTRY_KW = ["生态修复", "地质勘查", "地质灾害", "矿山治理", "水土保持", "勘察", "设计", "监理"]
_DEFAULT_REGIONS = ["四川", "西藏", "新疆"]

# 意向项目类型英文编码 → 中文标签(展示用)
_PROJECT_TYPE_LABELS = {
    "energy": "能源", "transport": "交通", "mining_rights": "矿业权", "ecology": "生态修复",
    "water": "水利", "construction": "工程建设", "land": "土地整治", "urban": "市政",
    "education": "教育", "medical": "医疗卫生", "agriculture": "农业", "environment": "环保",
    "geology": "地质勘查", "disaster": "灾害防治", "mining": "矿山治理", "soil": "水土保持",
}


def _industry_keywords(db: Session) -> list:
    from app.services.geo_monitor import get_industry_keywords
    return get_industry_keywords(db) or _DEFAULT_INDUSTRY_KW


def _brand_names(db: Session) -> list:
    from app.services.geo_monitor import get_brand_names
    return get_brand_names(db) or []


# ── 商机评分 ──────────────────────────────────────────────

def score_opportunities(db: Session, days: int = 30, limit: int = 50) -> dict:
    """跨 意向/招标/中标 三源评分商机。

    评分维度: 关键词命中(行业词, 各 +3) + 地域命中(重点地域 +2) + 时效(近7天 +2) + 金额(有预算 +1)。
    返回按分数排序的商机列表(含推荐理由)。
    """
    from app.models.intent_notice import IntentNotice
    from app.models.web_clue import WebClue
    from app.models.bid_notice import BidNotice

    cutoff = datetime.now() - timedelta(days=days)
    kws = _industry_keywords(db)
    regions = _DEFAULT_REGIONS

    items = []

    def hit_score(text: str) -> tuple:
        hit = [k for k in kws if k and k in (text or "")]
        region_hit = [r for r in regions if r in (text or "")]
        return hit, region_hit

    # 意向
    for it in db.execute(
        select(IntentNotice).where(
            IntentNotice.is_deleted == False, IntentNotice.status != "expired",
            IntentNotice.published_at >= cutoff,
        )
    ).scalars().all():
        text = f"{it.title or ''} {it.project_type or ''} {it.region or ''} {it.industry or ''}"
        hit, region_hit = hit_score(text)
        if not hit and not region_hit:
            continue
        score = len(hit) * 3 + (2 if region_hit else 0) + (2 if (it.published_at or datetime.min) >= datetime.now() - timedelta(days=7) else 0) + (1 if it.amount else 0)
        items.append({
            "source": "意向", "source_label": "投资意向期",
            "id": it.id, "title": it.title, "url": it.url or "",
            "region": it.region or it.province or "", "amount": float(it.amount) if it.amount else None,
            "published_at": it.published_at.strftime("%Y-%m-%d") if it.published_at else "",
            "keywords": hit[:5], "score": score,
            "reason": "命中关键词:" + "、".join(hit[:3]) + ("; 重点地域:" + "、".join(region_hit[:2]) if region_hit else ""),
        })

    # 招标线索
    for c in db.execute(
        select(WebClue).where(
            WebClue.is_deleted == False, WebClue.status == "accepted", WebClue.published_at >= cutoff,
        )
    ).scalars().all():
        text = f"{c.title or ''} {c.summary or ''} {c.region or ''}"
        hit, region_hit = hit_score(text)
        if not hit and not region_hit:
            continue
        score = len(hit) * 3 + (2 if region_hit else 0) + (2 if (c.published_at or datetime.min) >= datetime.now() - timedelta(days=7) else 0)
        items.append({
            "source": "招标", "source_label": "招标期",
            "id": c.id, "title": c.title, "url": c.url or "",
            "region": c.region or "", "amount": None,
            "published_at": c.published_at.strftime("%Y-%m-%d") if c.published_at else "",
            "keywords": hit[:5], "score": score,
            "reason": "命中关键词:" + "、".join(hit[:3]) + ("; 重点地域:" + "、".join(region_hit[:2]) if region_hit else ""),
        })

    # 中标(观察采购人动向)
    for b in db.execute(
        select(BidNotice).where(BidNotice.is_deleted == False, BidNotice.published_at >= cutoff)
    ).scalars().all():
        text = f"{b.title or ''} {b.purchaser or ''} {b.region or ''}"
        hit, region_hit = hit_score(text)
        if not hit and not region_hit:
            continue
        score = len(hit) * 2 + (2 if region_hit else 0)
        items.append({
            "source": "中标", "source_label": "中标公示期",
            "id": b.id, "title": b.title, "url": b.url or "",
            "region": b.region or "", "amount": None,
            "published_at": b.published_at.strftime("%Y-%m-%d") if b.published_at else "",
            "keywords": hit[:5], "score": score,
            "reason": "采购人动向:" + (b.purchaser or "")[:30],
        })

    items.sort(key=lambda x: (-x["score"], x["published_at"] or ""), reverse=False)
    items.sort(key=lambda x: -x["score"])
    return {"total": len(items), "items": items[:limit], "industry_keywords": kws}


# ── 内容选题推荐 ──────────────────────────────────────────

def suggest_topics(db: Session) -> dict:
    """选题推荐: 结合 GEO 引用缺口 + 关键词可见度缺口 + 数据热点。"""
    from app.models.geo import GeoMention, GeoKeyword

    topics = []

    # 1) 数据热点(近90天中标/意向 TOP 主题)
    stats = _quick_stats(db)
    for r in (stats.get("intent_types") or [])[:3]:
        topics.append({
            "source": "data_hot", "title": f"「{r['name']}」项目机会分析",
            "rationale": f"近90天意向项目中「{r['name']}」出现 {r['count']} 次, 属于市场热点, 值得产出一篇解读内容抢占 AI 引用。",
            "kind": "article", "priority": 8,
        })

    # 2) GEO 可见度缺口: 监测词被问到但从未提及本公司 → 重点补内容
    kws = db.execute(select(GeoKeyword).where(GeoKeyword.is_deleted == False)).scalars().all()
    for kw in kws[:5]:
        mentions = db.execute(
            select(GeoMention).where(GeoMention.keyword_id == kw.id, GeoMention.is_deleted == False)
        ).scalars().all()
        parsed = [m for m in mentions if m.status == "parsed"]
        visible = [m for m in parsed if m.self_visible]
        if parsed and not visible:
            topics.append({
                "source": "geo_gap", "title": f"「{kw.keyword}」可见度为零 — 需内容补位",
                "rationale": f"该监测词被问 {len(parsed)} 次, AI 均未提及本公司。建议围绕该词产出一篇带数据的权威内容, 提升被引用概率。",
                "kind": "faq", "priority": 9,
            })

    # 3) 引用源缺口: AI 高频引用的外部源, 我们可产同主题自有内容
    cited = _cited_source_domains(db)
    for dom, cnt in list(cited.items())[:3]:
        topics.append({
            "source": "cite_gap", "title": f"对标高频引用源「{dom}」产出自有数据内容",
            "rationale": f"AI 在近30天回答中高频引用 {dom}({cnt} 次), 说明该主题内容需求大, 平台数据可支撑更权威的自有版本。",
            "kind": "industry_report", "priority": 7,
        })

    topics.sort(key=lambda x: -x["priority"])
    return {"topics": topics[:10], "total": len(topics)}


def _quick_stats(db: Session) -> dict:
    from app.models.intent_notice import IntentNotice
    cutoff = datetime.now() - timedelta(days=90)
    intents = db.execute(
        select(IntentNotice).where(IntentNotice.is_deleted == False, IntentNotice.published_at >= cutoff)
    ).scalars().all()
    counter: dict = {}
    for i in intents:
        t = (i.project_type or "").strip()
        if t:
            label = _PROJECT_TYPE_LABELS.get(t, t)
            counter[label] = counter.get(label, 0) + 1
    return {"intent_types": [{"name": k, "count": v} for k, v in sorted(counter.items(), key=lambda x: -x[1])[:10]]}


def _cited_source_domains(db: Session) -> dict:
    from app.models.geo import GeoMention
    cutoff = datetime.now() - timedelta(days=30)
    mentions = db.execute(
        select(GeoMention).where(GeoMention.is_deleted == False, GeoMention.asked_at >= cutoff)
    ).scalars().all()
    counter: dict = {}
    for m in mentions:
        for s in (m.cited_sources or []):
            d = s.get("domain") or ""
            if d:
                counter[d] = counter.get(d, 0) + 1
    return dict(sorted(counter.items(), key=lambda x: -x[1]))


# ── 闭环看板 ──────────────────────────────────────────────

def marketing_dashboard(db: Session, days: int = 30) -> dict:
    """营销智能体总览: 感知/决策/执行/反馈 四环数据聚合。"""
    from app.services.geo_monitor import dashboard_stats
    from app.services.content_factory import content_stats

    geo = dashboard_stats(db, days=days)
    content = content_stats(db)
    opp = score_opportunities(db, days=days, limit=10)
    topics = suggest_topics(db)

    return {
        "cycle": {
            "perceive": {"geo_mentions": geo["total_mentions"], "self_visible": geo["visible_count"],
                          "visible_ratio": geo["visible_ratio"]},
            "decide": {"opportunities": opp["total"], "topics": topics["total"]},
            "execute": {"content_total": content["total"], "published": content["published_count"],
                         "draft": _count_of(content["by_status"], "draft"),
                         "review": _count_of(content["by_status"], "review")},
            "feedback": {"cited_sources": len(geo["cited_sources"]), "mentioned_companies": len(geo["mentioned_top"]),
                          "content_cited": _content_cited_count(db)},
        },
        "geo": geo, "content": content,
        "opportunities": opp["items"][:10], "topics": topics["topics"][:10],
        "brand_names": _brand_names(db), "industry_keywords": _industry_keywords(db),
    }


def _content_cited_count(db: Session) -> int:
    """已被 AI 引用(有 GEO 反馈回链)的已发布内容数。"""
    from app.models.content import ContentAsset
    assets = db.execute(
        select(ContentAsset).where(
            ContentAsset.is_deleted == False, ContentAsset.status == "published"
        )
    ).scalars().all()
    return sum(1 for a in assets if (a.geo_feedback or {}).get("cite_count"))


def _count_of(rows: list, name: str) -> int:
    for r in rows:
        if r["name"] == name:
            return r["count"]
    return 0


# ── 基础数据种子(启动时幂等执行) ─────────────────────────

def seed_marketing_basics(db: Session) -> None:
    """初始化营销智能体基础数据: 发布渠道 / 默认AI引擎 / 默认监测关键词 / 品牌配置。

    全部幂等: 已存在则跳过。品牌词默认取 platform 空配置, 用户可在前端补充。
    """
    from app.services.content_factory import seed_channels
    from app.models.geo import GeoEngine, GeoKeyword

    seed_channels(db)

    # 默认 AI 引擎(适配器均从 manual 起步, 用户可按需切换 openai_api/crawl4ai)
    default_engines = [
        ("豆包", "doubao", "https://www.doubao.com/chat/", "manual",
         "字节跳动 AI 助手, 用户量大, 优先接入"),
        ("DeepSeek", "deepseek", "https://chat.deepseek.com/", "manual",
         "可接 OpenAI 兼容 API(api.deepseek.com)"),
        ("秘塔AI搜索", "metaso", "https://metaso.cn/", "manual",
         "AI 搜索, 回答带引用来源, GEO 参考价值高"),
        ("百度AI搜索", "baiduai", "https://chat.baidu.com/", "manual",
         "百度文小言/AI搜索, 国内搜索入口"),
        ("腾讯元宝", "tencent", "https://yuanbao.tencent.com/chat/", "manual",
         "腾讯 AI 助手"),
    ]
    for name, code, url, adapter, notes in default_engines:
        exists = db.execute(
            select(GeoEngine).where(GeoEngine.code == code)
        ).scalar_one_or_none()
        if not exists:
            db.add(GeoEngine(name=name, code=code, url=url, adapter=adapter, notes=notes, enabled=True))

    # Ollama 本地模型引擎(OpenAI 兼容接口): 用于自检「本地 AI 怎么看我们」/无网测试
    from app.config import settings
    ollama_ep = settings.OLLAMA_BASE_URL.rstrip("/") + "/v1/chat/completions"
    ollama_model = settings.OLLAMA_MODEL
    exists = db.execute(
        select(GeoEngine).where(GeoEngine.code == "ollama_local")
    ).scalar_one_or_none()
    if not exists:
        db.add(GeoEngine(
            name="Ollama 本地模型", code="ollama_local", url=settings.OLLAMA_BASE_URL,
            adapter="openai_api", api_endpoint=ollama_ep, api_key="ollama",
            api_model=ollama_model,
            notes="本地 Ollama 的 OpenAI 兼容接口, 用于自检与离线测试(无需外网密钥)",
            enabled=False,
        ))

    # 默认监测关键词(行业词, 品牌词矩阵由用户配置)
    default_keywords = [
        ("生态修复工程 招标 公司 推荐", None, "生态修复"),
        ("地质灾害治理 勘察设计 单位", None, "地灾防治"),
        ("矿山生态修复 治理 企业", None, "矿山治理"),
        ("地质勘查 服务 单位 资质", None, "地质勘查"),
        ("水土保持方案 编制 机构", None, "水土保持"),
    ]
    for kw, region, category in default_keywords:
        exists = db.execute(
            select(GeoKeyword).where(GeoKeyword.keyword == kw)
        ).scalar_one_or_none()
        if not exists:
            db.add(GeoKeyword(keyword=kw, region=region, category=category, priority=5, enabled=True))

    db.commit()
    logger.info("[marketing] 营销智能体基础数据种子完成")
