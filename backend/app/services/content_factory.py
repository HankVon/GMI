"""数据内容工厂 — 把中台数据自动生成「被 AI 引擎引用的内容资产」。

内容类型(kind):
  industry_report  行业数据报告(招标/中标/意向趋势统计 + LLM 撰写)
  faq              行业 FAQ(热点问题结构化问答, 适合 FAQPage 标记)
  company_profile  公司档案页(业绩/中标/资质, 实体一致性)
  article          通用文章(选题驱动)

流程: 生成(draft) → 提交审核(review) → 发布(published) / 驳回(rejected)。
Ollama 不可用时自动降级为「确定性模板」生成, 保证链路可用。
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.services.llm_enhance import LLMUnavailable, _generate

logger = logging.getLogger("content_factory")

KINDS = {
    "industry_report": {"label": "行业数据报告", "desc": "招标/中标/意向趋势统计 + AI 撰写"},
    "faq": {"label": "行业 FAQ", "desc": "热点问题结构化问答(FAQPage 友好)"},
    "company_profile": {"label": "公司档案页", "desc": "单位业绩/中标/资质画像(实体一致性)"},
    "article": {"label": "通用文章", "desc": "选题驱动的内容文章"},
}

DEFAULT_CHANNEL = "official_site"


# ── 数据统计 ──────────────────────────────────────────────

def collect_report_stats(db: Session, days: int = 365) -> dict:
    """从各业务表聚合行业统计数据(内容生成的依据, 可溯源)。"""
    from app.models.bid_notice import BidNotice
    from app.models.intent_notice import IntentNotice
    from app.models.web_clue import WebClue
    from app.models.company import Company

    cutoff = datetime.now() - timedelta(days=days)

    stats: dict = {"days": days, "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")}

    # 中标
    bids = db.execute(
        select(BidNotice).where(BidNotice.is_deleted == False, BidNotice.published_at >= cutoff)
    ).scalars().all()
    stats["bids"] = {
        "total": len(bids),
        "by_region": _top(_count(bids, lambda b: b.region), 10),
        "top_purchasers": _top(_count(bids, lambda b: b.purchaser), 8),
        "recent_titles": [{"title": b.title, "region": b.region or "", "purchaser": b.purchaser or ""}
                          for b in sorted(bids, key=lambda x: x.published_at or datetime.min, reverse=True)[:8]],
    }

    # 意向
    intents = db.execute(
        select(IntentNotice).where(IntentNotice.is_deleted == False, IntentNotice.published_at >= cutoff)
    ).scalars().all()
    stats["intents"] = {
        "total": len(intents),
        "by_type": _top(_count(intents, lambda i: i.project_type), 10),
        "by_province": _top(_count(intents, lambda i: i.province), 10),
        "amount_sum": round(float(sum((i.amount or 0) for i in intents)), 0),
    }

    # 线索(招标期)
    clues = db.execute(
        select(WebClue).where(
            WebClue.is_deleted == False, WebClue.status == "accepted", WebClue.published_at >= cutoff
        )
    ).scalars().all()
    stats["clues"] = {
        "total": len(clues),
        "by_category": _top(_count(clues, lambda c: c.category), 10),
    }

    # 企业库
    companies = db.execute(select(Company).where(Company.is_deleted == False)).scalars().all()
    stats["companies"] = {"total": len(companies)}

    return stats


def _count(items, key_fn) -> dict:
    out: dict = {}
    for it in items:
        k = key_fn(it)
        if not k:
            continue
        k = str(k).strip()
        out[k] = out.get(k, 0) + 1
    return out


def _top(counter: dict, n: int) -> list:
    return [{"name": k, "count": v} for k, v in sorted(counter.items(), key=lambda x: -x[1])[:n]]


def _stats_to_markdown(stats: dict) -> str:
    """把统计 JSON 转成 Markdown 片段(降级模板也用它)。"""
    lines = []
    bids, intents = stats.get("bids", {}), stats.get("intents", {})
    lines.append(f"**数据窗**: 近 {stats.get('days', 365)} 天(统计截至 {stats.get('generated_at', '')})")
    lines.append("")
    lines.append(f"### 中标公告({bids.get('total', 0)} 条)")
    if bids.get("by_region"):
        lines.append("- 区域分布: " + "、".join(f"{r['name']}({r['count']})" for r in bids["by_region"][:6]))
    if bids.get("top_purchasers"):
        lines.append("- 主要采购人: " + "、".join(f"{r['name']}({r['count']})" for r in bids["top_purchasers"][:5]))
    lines.append("")
    lines.append(f"### 意向项目({intents.get('total', 0)} 条, 预算合计 {intents.get('amount_sum', 0):.0f} 万元)")
    if intents.get("by_type"):
        lines.append("- 项目类型: " + "、".join(f"{r['name']}({r['count']})" for r in intents["by_type"][:6]))
    if intents.get("by_province"):
        lines.append("- 地域分布: " + "、".join(f"{r['name']}({r['count']})" for r in intents["by_province"][:6]))
    lines.append("")
    lines.append(f"### 招标线索({stats.get('clues', {}).get('total', 0)} 条)")
    clues = stats.get("clues", {})
    if clues.get("by_category"):
        lines.append("- 分类: " + "、".join(f"{r['name']}({r['count']})" for r in clues["by_category"][:6]))
    if bids.get("recent_titles"):
        lines.append("")
        lines.append("### 近期代表性中标")
        for r in bids["recent_titles"][:5]:
            lines.append(f"- {r['title']}（{r['region']} · {r['purchaser']}）")
    return "\n".join(lines)


# ── LLM 生成(带模板降级) ─────────────────────────────────

def _llm(db: Session, prompt: str, timeout: float = 240.0) -> Optional[str]:
    """调用 Ollama(模型取 mk_config.llm_model, 可前端配置), 不可用返回 None。"""
    from app.services.geo_monitor import get_agent_model
    try:
        return _generate(prompt, timeout=timeout, model=get_agent_model(db))
    except LLMUnavailable:
        logger.warning("ollama 不可用, 内容生成降级为模板")
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM 生成异常: %s", e)
        return None


def _generate_industry_report(db: Session, params: dict) -> dict:
    """行业数据报告: 统计 → LLM 撰写 → (降级)模板。"""
    days = int(params.get("days") or 365)
    stats = collect_report_stats(db, days=days)
    data_md = _stats_to_markdown(stats)
    region_hint = f"重点地域: {params.get('region')}。" if params.get("region") else ""
    prompt = (
        "你是地质/生态修复行业的产业分析师。请根据以下真实统计数据, 撰写一份面向"
        "【政府采购决策者与同行企业】的行业简报(中文, Markdown), 包含:\n"
        "1. 总体形势(2-3句)\n"
        "2. 市场机会分析(结合区域/项目类型/预算, 给出可操作洞察)\n"
        "3. 建议关注方向(3-5条, 具体)\n"
        "要求: 只引用数据中的事实, 不要编造数字; 语气专业务实。\n\n"
        f"{region_hint}\n统计数据:\n{data_md}"
    )
    content = _llm(db, prompt)
    title = f"生态地质行业简报（{datetime.now().strftime('%Y-%m')}）"
    if content is None:
        content = (
            f"# {title}\n\n> 本报告由 SSM 营销智能体基于平台真实数据自动生成(LLM 不可用, 使用确定性模板)。\n\n"
            f"{data_md}\n\n---\n\n### 洞察与建议\n"
            "- 建议持续跟踪上表头部区域与采购人的新公告(平台已支持 意向/招标/中标 三阶段监控)。\n"
            "- 针对高频采购人, 可利用平台人脉库定位关键决策人与合作渠道。\n"
        )
    return {"title": title, "content": content, "summary": f"近 {days} 天行业数据简报, 中标 {stats['bids']['total']} 条、意向 {stats['intents']['total']} 条。",
            "source_data": stats, "kind": "industry_report"}


def _generate_faq(db: Session, params: dict) -> dict:
    """行业 FAQ: 从行业关键词 + 近期公告提炼问答。"""
    from app.services.geo_monitor import get_industry_keywords
    kws = get_industry_keywords(db) or ["生态修复", "地质勘查", "地质灾害防治", "矿山治理", "水土保持"]
    topic = (params.get("topic") or "").strip()
    base = topic or "、".join(kws[:5])
    prompt = (
        f"围绕【{base}】为政府采购/招投标场景撰写 5 条高频问答(中文)。\n"
        "每条格式: 问: 问题; 答: 专业且简洁的回答(80-150字, 可提及资质/流程/标准)。\n"
        "只输出问答文本, 不要多余说明。"
    )
    content = _llm(db, prompt, timeout=180)
    if content is None:
        content = "\n\n".join(
            f"问: {k}项目招标需要什么资质?\n答: 视项目类型而定, 一般需具备相应行业资质与类似业绩, 具体以招标公告要求为准(可通过平台情报中心检索最新公告)。"
            for k in kws[:5]
        )
    title = f"{base} 常见问题解答（FAQ）"
    return {"title": title, "content": content,
            "summary": f"围绕「{base}」的 {5} 条行业问答, 结构化格式利于 FAQPage 标记。",
            "source_data": {"keywords": kws, "topic": topic}, "kind": "faq"}


def _generate_company_profile(db: Session, params: dict) -> dict:
    """公司档案页: 单位信息 + 中标业绩 → 实体一致的画像内容。"""
    from app.models.company import Company
    from app.models.bid_notice import BidNotice

    company_id = int(params.get("company_id") or 0)
    company = db.get(Company, company_id) if company_id else None
    if not company:
        raise ValueError("company_id 无效或单位不存在")
    ext = company.ext_attrs or {}
    bids = db.execute(
        select(BidNotice).where(BidNotice.is_deleted == False)
    ).scalars().all()
    own_bids = []
    for b in bids:
        if b.purchaser_company_id == company.id:
            own_bids.append({"role": "采购人", "title": b.title, "region": b.region or "", "date": b.published_at.strftime("%Y-%m-%d") if b.published_at else ""})
        else:
            for s in (b.meta or {}).get("suppliers", []):
                if s.get("supplier_company_id") == company.id:
                    own_bids.append({"role": "中标供应商", "title": b.title, "region": b.region or "",
                                     "date": b.published_at.strftime("%Y-%m-%d") if b.published_at else ""})
    info = {
        "name": company.name, "short_name": company.short_name or "", "province": company.province or "",
        "city": company.city or "", "industry": company.industry or "", "website": company.website or "",
        "address": company.address or "", "legal_rep": ext.get("legal_rep") or "",
        "business_scope": ext.get("business_scope") or "", "summary": ext.get("summary") or "",
    }
    bids_md = "\n".join(f"- [{b['role']}] {b['title']}（{b['region']} · {b['date']}）" for b in own_bids[:10]) or "- (暂无平台内业绩记录)"
    prompt = (
        "你是企业品牌内容编辑。基于以下单位真实信息, 撰写一段 300-500 字的中文公司简介"
        "(用于官网与 AI 收录, 需事实准确、实体信息一致, 不要编造), 可分 2-3 段。\n\n"
        f"单位信息: {json.dumps(info, ensure_ascii=False)}\n业绩记录:\n{bids_md}"
    )
    content = _llm(db, prompt, timeout=180)
    if content is None:
        content = (
            f"# {company.name}\n\n"
            f"{ext.get('summary') or company.name + ' 是一家注册于 ' + (company.province or '') + (company.city or '') + ' 的单位, 所属行业: ' + (company.industry or '未分类') + '。'}\n\n"
            f"### 平台业绩记录\n{bids_md}"
        )
    title = f"{company.name} - 企业档案"
    return {"title": title, "content": content,
            "summary": f"{company.name} 企业档案(含 {len(own_bids)} 条平台业绩), 实体信息结构化, 利于 AI 引擎建立实体认知。",
            "source_data": {"company_id": company.id, "company_name": company.name, "info": info, "bids": own_bids},
            "kind": "company_profile"}


def _generate_article(db: Session, params: dict) -> dict:
    """通用文章: 按主题 + 数据佐证。"""
    topic = (params.get("topic") or "生态修复行业机会").strip()
    stats = collect_report_stats(db, days=90)
    data_md = _stats_to_markdown(stats)
    prompt = (
        f"请围绕主题【{topic}】撰写一篇 500-800 字的中文文章(Markdown, 含小标题), "
        "面向政府采购从业者, 观点务实, 可引用以下平台真实数据佐证(不要编造其他数字):\n\n" + data_md
    )
    content = _llm(db, prompt)
    if content is None:
        content = f"# {topic}\n\n> 本文由 SSM 营销智能体基于平台数据自动生成。\n\n{data_md}"
    return {"title": topic, "content": content, "summary": f"围绕「{topic}」的文章, 以平台数据佐证。",
            "source_data": {"topic": topic, "stats": stats}, "kind": "article"}


_GENERATORS = {
    "industry_report": _generate_industry_report,
    "faq": _generate_faq,
    "company_profile": _generate_company_profile,
    "article": _generate_article,
}


# ── 生成与流转 ────────────────────────────────────────────

def generate_content(db: Session, kind: str, params: dict, user: Optional[dict] = None) -> dict:
    """生成内容并落库为 draft。返回 {id, title, kind, content}。"""
    from app.models.content import ContentAsset, ContentChannel

    if kind not in _GENERATORS:
        raise ValueError(f"不支持的内容类型: {kind}, 可选: {list(_GENERATORS.keys())}")
    gen = _GENERATORS[kind](db, params or {})

    channel_code = (params.get("channel") or DEFAULT_CHANNEL).strip()
    channel = db.execute(
        select(ContentChannel).where(ContentChannel.code == channel_code, ContentChannel.is_deleted == False)
    ).scalar_one_or_none()

    asset = ContentAsset(
        title=gen["title"], kind=kind, content=gen["content"], summary=gen.get("summary"),
        source_data=gen.get("source_data"), status="draft",
        channel=channel.code if channel else channel_code,
        channel_name=channel.name if channel else channel_code,
        created_by=(user or {}).get("id") or 0,
        created_by_name=(user or {}).get("display_name") or (user or {}).get("username") or "营销智能体",
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return {"id": asset.id, "title": asset.title, "kind": asset.kind, "status": asset.status,
            "content": asset.content, "summary": asset.summary}


def submit_for_review(db: Session, asset_id: int) -> dict:
    from app.models.content import ContentAsset
    asset = db.get(ContentAsset, asset_id)
    if not asset or asset.is_deleted:
        raise ValueError("内容不存在")
    if asset.status != "draft":
        raise ValueError(f"仅草稿可提交审核, 当前状态: {asset.status}")
    asset.status = "review"
    db.commit()
    return {"id": asset.id, "status": asset.status}


def approve(db: Session, asset_id: int, published_url: str = "") -> dict:
    from app.models.content import ContentAsset
    asset = db.get(ContentAsset, asset_id)
    if not asset or asset.is_deleted:
        raise ValueError("内容不存在")
    if asset.status not in ("review", "draft"):
        raise ValueError(f"仅待审核/草稿可发布, 当前状态: {asset.status}")
    asset.status = "published"
    asset.published_at = datetime.now()
    if published_url:
        asset.published_url = published_url
    elif asset.channel:
        asset.published_url = f"{asset.channel}://content/{asset.id}"
    else:
        asset.published_url = f"content://{asset.id}"
    db.commit()
    return {"id": asset.id, "status": asset.status, "published_url": asset.published_url}


def reject(db: Session, asset_id: int, comment: str = "") -> dict:
    from app.models.content import ContentAsset
    asset = db.get(ContentAsset, asset_id)
    if not asset or asset.is_deleted:
        raise ValueError("内容不存在")
    if asset.status != "review":
        raise ValueError(f"仅待审核可驳回, 当前状态: {asset.status}")
    asset.status = "rejected"
    asset.review_comment = comment
    db.commit()
    return {"id": asset.id, "status": asset.status}


def content_stats(db: Session) -> dict:
    """内容工厂看板统计。"""
    from app.models.content import ContentAsset
    assets = db.execute(select(ContentAsset).where(ContentAsset.is_deleted == False)).scalars().all()
    status_counter = _count(assets, lambda a: a.status)
    kind_counter = _count(assets, lambda a: a.kind)
    published = [a for a in assets if a.status == "published"]
    return {
        "total": len(assets),
        "by_status": [{"name": k, "count": v} for k, v in sorted(status_counter.items(), key=lambda x: -x[1])],
        "by_kind": [{"name": k, "count": v} for k, v in sorted(kind_counter.items(), key=lambda x: -x[1])],
        "published_count": len(published),
        "recent": [{"id": a.id, "title": a.title, "kind": a.kind, "status": a.status,
                    "channel": a.channel_name or "", "created_at": a.created_at.strftime("%Y-%m-%d %H:%M"),
                    "published_at": a.published_at.strftime("%Y-%m-%d %H:%M") if a.published_at else ""}
                   for a in sorted(assets, key=lambda x: x.created_at, reverse=True)[:10]],
    }


def seed_channels(db: Session) -> None:
    """初始化默认发布渠道(幂等)。"""
    from app.models.content import ContentChannel
    defaults = [
        ("官网", "official_site", "https://example.com/"),
        ("微信公众号", "wechat", "https://mp.weixin.qq.com/s/"),
        ("知乎专栏", "zhihu", "https://zhuanlan.zhihu.com/p/"),
        ("百家号", "baijiahao", "https://baijiahao.baidu.com/s?id="),
    ]
    for name, code, url_prefix in defaults:
        exists = db.execute(
            select(ContentChannel).where(ContentChannel.code == code)
        ).scalar_one_or_none()
        if not exists:
            db.add(ContentChannel(name=name, code=code, url_prefix=url_prefix))
    db.commit()
