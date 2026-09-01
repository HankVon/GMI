"""意向性信息 API — 政务源意向项目结构化展示/筛选/爬取触发。"""
import asyncio
import json
import re
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.intent_notice import IntentNotice
from app.models.project import Project
from app.models.project_clue import ProjectClue
from app.models.project_progress import ProjectProgress
from app.models.option_set import OptionSet, OptionItem
from app.services import project_tracker as tracker
from app.config import settings

router = APIRouter(prefix="/intent", tags=["意向信息"])

# 后台(登录态) AI 研判 prompt — 允许输出真实单位/人员名(授权环境)
_INTENT_AI_PROMPT = """你是资深招投标与商务情报分析师。请基于以下【真实招标意向】信息，给出专业、可操作的研判分析。
请严格只输出 JSON（不要 markdown 代码块、不要任何额外文字），格式：
{{
  "summary": "一句话研判核心",
  "heat": 0-100 的整数（综合金额、时效性、行业热度评估的意向热度）,
  "heat_source": "一句话说明该热度的评分依据(如金额档位、发布时间、行业热度)",
  "coop_prob": 0-100 的整数（基于平台人脉触达可能性估算的合作概率）,
  "coop_source": "一句话说明该概率的估算依据(如关联实体数、匹配得分、是否已识别业主)",
  "parties": ["涉及的关键单位/业主名称(真实)", "关键人员(真实姓名或角色)"],
  "network_path": "基于平台人脉图谱的触达路径与桥接人建议(可引用真实单位/人员)",
  "advice": ["具体可执行建议1", "建议2", "建议3"],
  "opportunities": ["潜在合作机会1", "机会2"]
}}
全程简体中文。

# 意向信息
标题：{title}
发布部门：{dept}
地域：{region}
行业：{industry}
金额：{amount}
状态：{status}
关键词：{keywords}
关联单位/人员：{parties_hint}
原文摘要：{excerpt}"""


# 业务关键词(用于解释「为什么是意向信息」, 与 intent_crawler._BUSINESS_KEYWORDS 对齐)
_BUSINESS_KW_LABEL = {
    "地质灾害": "地质灾害治理", "地灾": "地质灾害治理", "滑坡": "地质灾害治理", "泥石流": "地质灾害治理",
    "崩塌": "地质灾害治理", "地面塌陷": "地质灾害治理", "隐患治理": "地质灾害治理", "排危": "地质灾害治理",
    "避险搬迁": "地质灾害治理", "边坡治理": "地质灾害治理",
    "生态修复": "生态修复", "生态治理": "生态修复", "环境治理": "生态修复", "矿山修复": "矿山生态修复",
    "矿山地质": "矿山生态修复", "恢复治理": "生态修复", "水土保持": "水土保持", "水土流失": "水土保持",
    "地质勘察": "地质勘察", "地质勘查": "地质勘察", "工程勘察": "地质勘察", "岩土": "地质勘察",
    "钻探": "地质勘察", "监测预警": "地质监测", "地质环境监测": "地质监测", "测绘": "测绘",
    "地灾评估": "地灾评估", "危险性评估": "地灾评估", "勘查设计": "勘查设计", "勘察设计": "勘查设计",
}
_TYPE_LABEL = {
    "geo_hazard": "地质灾害治理", "geo_survey": "地质勘察/监测", "eco_restoration": "生态修复",
    "mining_rights": "矿业权", "water": "水利", "transport": "交通", "energy": "能源",
}


def _hit_keywords(it) -> list:
    """返回标题/正文命中的业务关键词(去重, 保序)。"""
    text = f"{it.title or ''}\n{it.raw_text or ''}"
    return [k for k in _BUSINESS_KW_LABEL if k in text]


def _parse_matched_entity(raw):
    """解析 matched_entity JSON → dict。"""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return None


def _build_intent_reason(it) -> list:
    """自动生成「为什么这条可作为意向信息」的可解释理由列表。

    维度:
      1. 业务命中: 标题/正文命中的业务关键词(地灾/生态/矿山/勘察等)
      2. 项目类型: 识别出的类型(地质灾害治理/地质勘察/生态修复)
      3. 单位匹配: 解析出的项目业主/建设单位 是否已匹配到 company 库
      4. 地域价值: 是否为目标省份(四川/西藏/新疆)
      5. 金额: 是否带预算金额
      6. 权威来源: 来源(发改委/自然资源厅等)类型
      7. 时效: 发布时间
    返回 reason 字符串列表(前端直接展示为「意向理由」)。
    """
    reasons = []
    hits = _hit_keywords(it)
    if hits:
        labels = list(dict.fromkeys(_BUSINESS_KW_LABEL[k] for k in hits))
        reasons.append(f"命中业务关键词「{'、'.join(labels)}」，与公司业务直接相关")
    if it.project_type:
        lbl = _TYPE_LABEL.get(it.project_type) or it.industry or it.project_type
        reasons.append(f"识别为「{lbl}」类项目")
    if it.dept:
        reasons.append(f"由「{it.dept}」发布")
    me = _parse_matched_entity(it.matched_entity)
    if me and me.get("unit"):
        if me.get("matched"):
            reasons.append(f"项目单位「{me['unit']}」已在公司库匹配（{me.get('company', '')}）")
        else:
            reasons.append(f"解析出项目单位「{me['unit']}」")
        if me.get("doc_no"):
            reasons.append(f"批复文号 {me['doc_no']}")
    if it.amount:
        reasons.append(f"带预算金额 {float(it.amount):,.0f} 万元")
    if it.region:
        reasons.append(f"项目地域 {it.region}，属目标省份（四川/西藏/新疆）")
    if it.published_at:
        reasons.append(f"发布于 {it.published_at:%Y-%m-%d}，近 {it.published_at:%b} 信息")
    if it.keywords:
        reasons.append(f"来源关键词配置命中")
    if not reasons:
        reasons.append("结构化解析待完善，建议人工复核")
    return reasons


@router.get("/list")
async def intent_list(
    project_type: Optional[str] = Query(None, description="项目类型过滤"),
    region: Optional[str] = Query(None, description="地域过滤(省核心词/市核心词/县核心词, 兼容三级)"),
    province: Optional[str] = Query(None, description="省过滤(核心词: 四川/西藏/新疆)"),
    city: Optional[str] = Query(None, description="市过滤(核心词: 成都/日喀则/喀什)"),
    county: Optional[str] = Query(None, description="县过滤(核心词: 喜德/普兰/定日)"),
    keyword: Optional[str] = Query(None, description="标题/部门/采购人模糊搜索"),
    min_amount: Optional[float] = Query(None, description="金额下限(万元)"),
    max_amount: Optional[float] = Query(None, description="金额上限(万元)"),
    days: Optional[int] = Query(90, description="时间窗(近N天)"),
    status: Optional[str] = Query(None, description="状态 new/qualified/skip/expired"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """意向性项目列表(结构化筛选)。"""
    from datetime import datetime, timedelta
    from sqlalchemy import or_
    stmt = select(IntentNotice).where(IntentNotice.is_deleted == False)
    if keyword:
        stmt = stmt.where(or_(IntentNotice.title.contains(keyword), IntentNotice.dept.contains(keyword)))
    if project_type:
        stmt = stmt.where(IntentNotice.project_type == project_type)
    if province:
        stmt = stmt.where(IntentNotice.province == province)
    if city:
        stmt = stmt.where(IntentNotice.city == city)
    if county:
        stmt = stmt.where(IntentNotice.county == county)
    if region:
        # 兼容旧参数: 按 region 文本/省/市 模糊
        stmt = stmt.where(
            (IntentNotice.region.contains(region))
            | (IntentNotice.city == region)
            | (IntentNotice.province == region)
            | (IntentNotice.county == region)
        )
    if min_amount is not None:
        stmt = stmt.where(IntentNotice.amount >= min_amount)
    if max_amount is not None:
        stmt = stmt.where(IntentNotice.amount <= max_amount)
    if days:
        cutoff = datetime.now() - timedelta(days=days)
        stmt = stmt.where(IntentNotice.published_at >= cutoff)
    if status:
        stmt = stmt.where(IntentNotice.status == status)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    stmt = stmt.order_by(IntentNotice.published_at.is_(None), IntentNotice.published_at.desc(), IntentNotice.id.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    items = db.execute(stmt).scalars().all()
    # 批量取来源名
    from app.models.web_source import WebSource
    src_ids = {i.source_id for i in items if i.source_id}
    src_map = {}
    if src_ids:
        for s in db.execute(select(WebSource).where(WebSource.id.in_(src_ids))).scalars().all():
            src_map[s.id] = s.name
    out = [{
        "id": i.id, "title": i.title, "url": i.url, "dept": i.dept,
        "project_type": i.project_type, "industry": i.industry,
        "amount": float(i.amount) if i.amount is not None else None,
        "region": i.region, "province": i.province, "city": i.city, "county": i.county,
        "contact": i.contact, "published_at": str(i.published_at or ""), "status": i.status,
        "source_name": src_map.get(i.source_id) or "",
        "reason": _build_intent_reason(i),
        "matched_entity": _parse_matched_entity(i.matched_entity),
        "hit_keywords": _hit_keywords(i),
        "body_excerpt": (i.raw_text or "")[:220],
    } for i in items]
    return {"success": True, "total": total, "items": out}


@router.get("/region-tree")
async def intent_region_tree(
    user: dict = Depends(get_current_user),
):
    """目标省份(四川/西藏/新疆) 省-市-县 三级树(前端地域级联选择器)。"""
    from app.services.china_regions import target_region_tree
    return {"success": True, "items": target_region_tree()}


@router.get("/stats")
async def intent_stats(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """意向统计(类型分布/数量)。"""
    rows = db.execute(
        select(IntentNotice.project_type, func.count())
        .where(IntentNotice.is_deleted == False)
        .group_by(IntentNotice.project_type)
    ).all()
    types = [{"type": r[0] or "未分类", "count": r[1]} for r in rows if r[0]]
    total = db.execute(
        select(func.count()).where(IntentNotice.is_deleted == False)
    ).scalar() or 0
    return {"success": True, "total": total, "types": types}


@router.get("/winners")
async def intent_winners(
    days: int = Query(0, ge=0, description="时间窗(近N天, 0=全部)"),
    min_count: int = Query(2, ge=1, description="最少中标次数(2=只看常客)"),
    keyword: Optional[str] = Query(None, description="单位名关键字过滤"),
    region: Optional[str] = Query(None, description="区域关键字过滤(省/市)"),
    sort: str = Query("count", description="排序: count中标次数/amount累计金额/last最近中标"),
    limit: int = Query(50, ge=1, le=200, description="返回条数"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """中标活跃单位榜 — 从海量招标中标公告挖掘「经常中标/拿到项目」的单位。

    数据源: bid_notice.meta.suppliers(爬虫已结构化解析的中标供应商)。
    聚合: 中标次数 / 累计金额 / 最近中标时间 / 活跃月份 / 覆盖采购人与区域。
    关联: 按名称匹配 company 表补全单位画像。
    """
    from app.services.winner_mining import mine_winners
    return mine_winners(
        db,
        days=days,
        min_count=min_count,
        keyword=keyword or "",
        region=region or "",
        sort=sort,
        limit=limit,
    )


@router.get("/winner-opportunities")
async def winner_opportunities(
    name: str = Query(..., description="中标单位名称(精确归一化匹配)"),
    days: int = Query(365, ge=0, description="意向时间窗(近N天, 0=全部)"),
    limit: int = Query(20, ge=1, le=50, description="返回条数"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """反向关联: 某个中标活跃单位 → 它可能关注的新意向项目。

    该单位在 XX 市/县 多次中标 → 同市/县 新立项的意向项目, 大概率会去投标;
    历史中标标题里的业务词 命中意向标题 → 加分。
    返回按匹配分数排序的意向项目列表(含可解释的匹配原因)。
    """
    from app.services.winner_mining import mine_winner_opportunities
    return mine_winner_opportunities(db, name=name, days=days, limit=limit)


@router.post("/crawl")
async def intent_crawl(
    source_id: Optional[int] = Query(None, description="指定来源id, 不传则爬全部 intent 来源"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_project_crud")),
):
    """触发意向源爬取(政务源列表→详情→结构化→入库)。"""
    from app.services.intent_crawler import crawl_intent_source, crawl_all_intent_sources
    from app.models.web_source import WebSource
    if source_id:
        src = db.get(WebSource, source_id)
        if not src or src.is_deleted:
            raise HTTPException(status_code=404, detail="source not found")
        result = crawl_intent_source(db, src)
        return {"success": True, "data": result}
    result = crawl_all_intent_sources(db)
    return {"success": True, "data": result}


@router.get("/scout/targets")
async def scout_targets(
    days: int = Query(180, ge=1, le=730),
    top_n: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """推理引擎: 从项目库/人脉/中标推导高价值目标单位 × 意向检索关键词。"""
    from app.services.opportunity_scout import scout_targets as _scout
    return {"success": True, "data": _scout(db, days=days, top_n=top_n)}


@router.get("/scout/summary")
async def scout_summary(
    days: int = Query(180, ge=1, le=730),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """侦察摘要: 目标数/高优先/业务命中/来源分布。"""
    from app.services.opportunity_scout import scout_summary as _summary
    return {"success": True, "data": _summary(db, days=days)}


@router.get("/intent-detail/{intent_id}")
async def intent_detail(
    intent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """意向详情: 结构化字段 + 原文摘要 + 意向理由。

    注意: 此路由必须放在所有静态路径(/list /stats /winners /scout/*)之后,
    否则会因路径参数 {intent_id} 拦截静态路径请求。
    """
    it = db.get(IntentNotice, intent_id)
    if not it or it.is_deleted:
        raise HTTPException(status_code=404, detail="意向不存在")
    from app.models.web_source import WebSource
    src = db.get(WebSource, it.source_id) if it.source_id else None
    # 人脉关联: 意向 → tender_match → 人/单位
    from app.models.business_network import TenderMatch
    rels = db.execute(
        select(TenderMatch).where(
            TenderMatch.intent_id == intent_id,
            TenderMatch.is_deleted == False,
            TenderMatch.is_expired == False,
        ).order_by(TenderMatch.score.desc())
    ).scalars().all()
    related = [{
        "entity_type": r.entity_type, "entity_id": r.entity_id,
        "entity_name": r.entity_name, "match_type": r.match_type,
        "match_reason": r.match_reason, "score": float(r.score or 0),
    } for r in rels]
    return {
        "success": True,
        "data": {
            "id": it.id, "title": it.title, "url": it.url, "dept": it.dept,
            "project_type": it.project_type, "industry": it.industry,
            "amount": float(it.amount) if it.amount is not None else None,
            "region": it.region, "province": it.province, "city": it.city, "county": it.county,
            "contact": it.contact, "published_at": str(it.published_at or ""), "status": it.status,
            "source_name": src.name if src else "",
            "keywords": it.keywords,
            "reason": _build_intent_reason(it),
            "matched_entity": _parse_matched_entity(it.matched_entity),
            "raw_text": it.raw_text or "",
            "related_people": [r for r in related if r["entity_type"] == "person"],
            "related_companies": [r for r in related if r["entity_type"] == "company"],
        },
    }


@router.get("/{intent_id}/tracker")
async def intent_tracker(
    intent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """该意向公告归整到的项目的真实跟踪线索(按阶段分组)。

    通过 ProjectClue(clue_type='intent', clue_id=intent_id) 反查 project_id,
    复用项目跟踪器逻辑(tracked_clues + 同类候选兜底)。无关联项目时返回空分组,
    前端据此显示空态。
    """
    from app.api.v1.project_tracker import _fallback_clues

    row = db.execute(
        select(ProjectClue.project_id).where(
            ProjectClue.clue_type == "intent",
            ProjectClue.clue_id == intent_id,
            ProjectClue.is_deleted == False,
        )
    ).scalar_one_or_none()
    if not row:
        return {"success": True, "total": 0, "groups": [], "fallback": False}
    project = db.get(Project, row)
    if not project:
        return {"success": True, "total": 0, "groups": [], "fallback": False}
    # 排除项目自身来源公告(已导入为项目本体), 避免「跟踪情报=项目本身」
    src = ((project.ext_attrs or {}).get("source") or "").strip()
    groups = tracker.tracked_clues(db, project.id)
    if src:
        for g in groups:
            g["items"] = [it for it in g["items"] if (it.get("url") or "").strip() != src]
        groups = [g for g in groups if g["items"]]
    # 兜底: 无正式归整线索时, 实时匹配同类外部公告作为候选, 并标记 fallback
    fallback = False
    if not groups:
        fb = _fallback_clues(db, project, src)
        if fb:
            groups = fb
            fallback = True
    total = sum(len(g["items"]) for g in groups)
    return {"success": True, "total": total, "groups": groups, "fallback": fallback}


def _progress_stages(db: Session) -> list[dict]:
    """项目进展里程碑的阶段定义(可配置)。

    阶段来自选项集 project_progress_stage, 由管理员在后台「选项集管理」维护
    (可增删改、排序、配色)。未配置或选项集不存在时返回空列表, 前端自动回退为
    按进展记录渲染的纵向时间线。
    """
    set_id = db.execute(
        select(OptionSet.id).where(
            OptionSet.code == "project_progress_stage",
            OptionSet.is_deleted == False,
        )
    ).scalar_one_or_none()
    if not set_id:
        return []
    rows = db.execute(
        select(OptionItem).where(
            OptionItem.option_set_id == set_id,
            OptionItem.is_deleted == False,
        ).order_by(OptionItem.sort_order, OptionItem.id)
    ).scalars().all()
    return [{
        "value": i.value,
        "label": i.label,
        "color": i.color,
        "sort_order": i.sort_order,
    } for i in rows]


@router.get("/{intent_id}/progress")
async def intent_progress(
    intent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """该意向关联项目的真实进展记录(ProjectProgress, 手动维护, 按日期倒序)。

    通过 ProjectClue(clue_type='intent') 反查 project_id; 无关联项目时返回空列表。
    """
    row = db.execute(
        select(ProjectClue.project_id).where(
            ProjectClue.clue_type == "intent",
            ProjectClue.clue_id == intent_id,
            ProjectClue.is_deleted == False,
        )
    ).scalar_one_or_none()
    if not row:
        return {"success": True, "items": []}
    project = db.get(Project, row)
    if not project:
        return {"success": True, "items": []}
    rows = db.execute(
        select(ProjectProgress).where(
            ProjectProgress.project_id == project.id,
            ProjectProgress.is_deleted == False,
        ).order_by(ProjectProgress.progress_date.desc())
    ).scalars().all()
    items = [{
        "id": r.id,
        "title": r.title or "",
        "content": r.content or "",
        "progress_date": r.progress_date.strftime("%Y-%m-%d") if r.progress_date else "",
        "sort_order": r.sort_order or 0,
    } for r in rows]
    # stages: 可配置的里程碑阶段定义(选项集 project_progress_stage)。
    # 前端据此渲染横向里程碑; 未配置时回退为按进展记录渲染的纵向时间线。
    return {"success": True, "items": items, "stages": _progress_stages(db)}


async def _llm_intent_analysis_backend(it: IntentNotice, related: list) -> dict | None:
    """后台(登录态)真实 LLM 研判 — 允许输出真实单位/人员名。失败返回 None。"""
    parties = "；".join(
        f"{r['entity_name']}({('人员' if r['entity_type'] == 'person' else '单位')})"
        for r in related[:12]
    ) or "（平台暂未匹配到人脉实体）"
    excerpt = (it.raw_text or "")[:400].replace("\n", " ")
    prompt = _INTENT_AI_PROMPT.format(
        title=it.title or "—",
        dept=it.dept or "—",
        region=it.region or "—",
        industry=it.industry or "相关行业",
        amount=(f"{float(it.amount):.0f}万" if it.amount is not None else "未披露"),
        status=it.status or "new",
        keywords="、".join((it.keywords or "").split(",")[:8]) or "—",
        parties_hint=parties,
        excerpt=excerpt or "—",
    )
    base_url = settings.OLLAMA_BASE_URL.rstrip("/")
    models = ["qwen2.5:7b", settings.OLLAMA_MODEL]
    for model in models:
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                resp = await client.post(
                    f"{base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "format": "json",
                        "keep_alive": -1,
                        "options": {"temperature": 0.4, "num_predict": 450},
                    },
                )
                resp.raise_for_status()
                content = resp.json()["message"]["content"]
            try:
                return json.loads(content)
            except Exception:
                m = re.search(r"\{.*\}", content, re.S)
                if m:
                    try:
                        return json.loads(m.group(0))
                    except Exception:
                        continue
        except Exception as e:  # noqa: BLE001
            print(f"[intent-ai] model={model} failed: {e!r}")
            continue
    return None


@router.post("/ai-analysis/{intent_id}")
async def intent_ai_analysis(
    intent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """后台·单条意向的真实 LLM 深度研判(登录态, 可展示真实单位/人员名)。

    注意: 路由需放在 /intent-detail/{intent_id} 之后(同为路径参数, 避免拦截)。
    LLM 较慢(弱算力约 1-2 分钟), 前端应展示 loading。
    """
    it = db.get(IntentNotice, intent_id)
    if not it or it.is_deleted:
        raise HTTPException(status_code=404, detail="意向不存在")
    from app.models.business_network import TenderMatch
    rels = db.execute(
        select(TenderMatch).where(
            TenderMatch.intent_id == intent_id,
            TenderMatch.is_deleted == False,
            TenderMatch.is_expired == False,
        ).order_by(TenderMatch.score.desc())
    ).scalars().all()
    related = [{
        "entity_type": r.entity_type, "entity_id": r.entity_id,
        "entity_name": r.entity_name,
    } for r in rels]

    analysis = await _llm_intent_analysis_backend(it, related)
    if analysis:
        return {
            "success": True,
            "data": {
                "source": "llm",
                "model": settings.OLLAMA_MODEL,
                "analysis": analysis,
                "note": "由本地大模型基于真实意向数据生成（后台授权环境，含真实单位/人员信息）。",
            },
        }
    # 降级: 规则引擎 — 多维真实数据计算(非固定值)
    from datetime import datetime as _dt
    level = "未披露"
    try:
        if it.amount is not None:
            v = float(it.amount)
            level = "1亿以上" if v >= 10000 else "2000万–1亿" if v >= 2000 else "500–2000万" if v >= 500 else "100–500万" if v >= 100 else "100万以下"
    except (TypeError, ValueError):
        pass
    # ── 意向热度 heat: 金额分档(基础) + 时效 + 状态 + 人脉关联度, 封顶 100 ──
    heat_base = {"未披露": 30, "100万以下": 35, "100–500万": 55, "500–2000万": 75, "2000万–1亿": 90, "1亿以上": 100}.get(level, 30)
    heat = heat_base
    if it.published_at:
        age_days = (_dt.now() - it.published_at).days
        if age_days <= 7:
            heat += 10          # 近一周: 高时效
        elif age_days <= 30:
            heat += 5           # 近一月: 较新
        elif age_days > 90:
            heat -= 5           # 超三月: 时效衰减
    if it.status == "new":
        heat += 5
    if it.province in ("四川", "西藏", "新疆"):
        heat += 3               # 目标省份加成
    heat = max(5, min(100, heat))
    # ── 合作概率 coop_prob: 基于真实人脉关联度, 5~95 ──
    n_related = len(rels)
    max_score = max((float(r.score or 0) for r in rels), default=0.0)
    has_unit = bool(it.matched_entity and '"company_id"' in (it.matched_entity or ""))
    coop = 20                                        # 基础
    coop += min(20, n_related * 8)                   # 匹配实体数: 每个 +8, 封顶 +20
    coop += int(max_score * 30)                      # 最高匹配得分(0~1)映射 0~30
    if has_unit:
        coop += 10                                   # 已锁定业主单位: 触达可行性更高
    if it.status == "expired":
        coop -= 15
    coop = max(5, min(95, coop))
    reasons = []
    if n_related:
        reasons.append(f"平台已匹配 {n_related} 个关联人脉实体")
    if max_score >= 0.7:
        reasons.append(f"最高匹配得分 {max_score:.2f}")
    if has_unit:
        reasons.append("已识别业主单位")
    reason_txt = ("；".join(reasons) + "。") if reasons else "暂无平台人脉关联，建议先建设触达路径。"
    return {
        "success": True,
        "data": {
            "source": "rule",
            "analysis": {
                "summary": f"基于规则引擎的研判（{it.region or '当地'}{it.industry or '相关'}类意向，金额{level}）。",
                "heat": heat,
                "coop_prob": coop,
                "heat_source": f"金额档位「{level}」({heat_base})+时效/状态/目标省份调整",
                "coop_source": reason_txt,
                "parties": [r["entity_name"] for r in related[:6]],
                "network_path": "建议结合平台人脉图谱定位与业主/主管部门存在弱关联的桥接人，分步建立联系。",
                "advice": [f"核实「{it.region or '当地'}」{it.industry or '相关'}类意向的决策链与业主单位，30 天内完成首次接洽。",
                           "通过平台人脉关系图谱定位可触达的桥接人，降低 cold-call 成本。",
                           "纳入商机库持续跟踪，关注同类型项目周期性投放窗口。"],
                "opportunities": ["同类项目周期性投放，可提前布局下一窗口期。"],
            },
            "note": f"本地大模型暂不可用，已回退至规则引擎分析。合作概率依据：{reason_txt}",
        },
    }


@router.get("/related-by-company/{company_id}")
async def related_by_company(
    company_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """机会标注: 某单位有望争取的意向项目(供单位详情页展示)。

    来源:
      1) tender_match.entity_id=company_id (业务/专长能力匹配 → 可争取机会)
      2) intent_notice.matched_entity 解析出 unit 已匹配此公司(与业主单位相关)
      3) intent_notice.dept 直接匹配单位名(该单位是采购/发布主体)
    """
    from app.models.business_network import TenderMatch
    from app.models.intent_notice import IntentNotice
    from app.models.company import Company
    comp = db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="单位不存在")
    items = []
    seen = set()
    # 1) tender_match 关联的 intent
    tm_rows = db.execute(
        select(TenderMatch).where(
            TenderMatch.entity_type == "company",
            TenderMatch.entity_id == company_id,
            TenderMatch.is_deleted == False,
            TenderMatch.intent_id.isnot(None),
        ).order_by(TenderMatch.score.desc())
    ).scalars().all()
    tm_intent_ids = [r.intent_id for r in tm_rows if r.intent_id]
    if tm_intent_ids:
        for it in db.execute(
            select(IntentNotice).where(
                IntentNotice.id.in_(tm_intent_ids), IntentNotice.is_deleted == False,
            ).order_by(IntentNotice.published_at.is_(None), IntentNotice.published_at.desc())
        ).scalars().all():
            if it.id in seen: continue
            seen.add(it.id)
            items.append({
                "id": it.id, "title": it.title, "url": it.url,
                "project_type": it.project_type, "industry": it.industry,
                "published_at": str(it.published_at or ""), "region": it.region,
                "matched_via": "tender_match",
                "match_reason": next((r.match_reason for r in tm_rows if r.intent_id == it.id), "人脉匹配推荐"),
                "score": float(next((r.score for r in tm_rows if r.intent_id == it.id), 0)),
            })
    # 2) matched_entity 关联
    me_rows = db.execute(
        select(IntentNotice).where(
            IntentNotice.is_deleted == False,
            IntentNotice.matched_entity.like(f'%\\"company_id\\": {company_id}%'),
        ).order_by(IntentNotice.published_at.desc()).limit(50)
    ).scalars().all()
    for it in me_rows:
        if it.id in seen: continue
        seen.add(it.id)
        me = _parse_matched_entity(it.matched_entity) or {}
        items.append({
            "id": it.id, "title": it.title, "url": it.url,
            "project_type": it.project_type, "industry": it.industry,
            "published_at": str(it.published_at or ""), "region": it.region,
            "matched_via": "project_unit",
            "match_reason": f"项目业主「{me.get('unit')}」与本公司相关，可争取对接",
            "score": 1.0,
        })
    # 3) dept 同名匹配
    if comp.name:
        dept_rows = db.execute(
            select(IntentNotice).where(
                IntentNotice.is_deleted == False,
                IntentNotice.dept == comp.name,
            ).order_by(IntentNotice.published_at.desc()).limit(50)
        ).scalars().all()
        for it in dept_rows:
            if it.id in seen: continue
            seen.add(it.id)
            items.append({
                "id": it.id, "title": it.title, "url": it.url,
                "project_type": it.project_type, "industry": it.industry,
                "published_at": str(it.published_at or ""), "region": it.region,
                "matched_via": "publisher",
                "match_reason": f"发布单位「{comp.name}」匹配",
                "score": 1.0,
            })
    return {"success": True, "company_id": company_id, "company_name": comp.name, "total": len(items), "items": items}


@router.get("/graph/{intent_id}")
async def intent_graph(
    intent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """意向专属子图: 以意向为中心, 返回关联单位/人员及其关系。

    优先从 Neo4j 查询(Intent 节点 + RELATES_TO 边); Neo4j 不可用或无边时
    降级到 MySQL(tender_match + matched_entity) 组装子图, 保证展示不空。
    返回: {center, nodes[], links[]}
      - center: 意向节点 {id, name, type:'intent', region, amount_wan, dept}
      - nodes: 关联实体(company/person)
      - links: 意向→实体 的 RELATES_TO 边
    """
    it = db.get(IntentNotice, intent_id)
    if not it or it.is_deleted:
        raise HTTPException(status_code=404, detail="意向不存在")

    center = {
        "id": f"INT{intent_id}", "name": it.title or "意向",
        "type": "intent", "region": it.region or "",
        "amount_wan": float(it.amount) if it.amount is not None else None,
        "dept": it.dept or "",
    }

    # 1) 优先 Neo4j
    try:
        from app.services import neo4j_sync as _nsync
        from app.config import settings as _st
        import neo4j as _neo4j
        driver = _nsync._get_driver()
        if driver is not None:
            with driver.session() as session:
                rec = session.run(
                    """
                    MATCH (i:Intent {intent_id: $intent_id})
                    OPTIONAL MATCH (i)-[r:RELATES_TO]->(e)
                    RETURN i.title AS title, i.region AS region, i.amount_wan AS amount_wan,
                           i.dept AS dept,
                           collect(CASE WHEN e IS NOT NULL THEN
                               {id: CASE WHEN e:Company THEN 'C' + toString(e.company_id)
                                         WHEN e:Person THEN 'P' + toString(e.person_id)
                                         ELSE 'X' END,
                                name: e.name, type: CASE WHEN e:Company THEN 'company'
                                                         WHEN e:Person THEN 'person' ELSE 'entity' END,
                                role: r.name_zh, confidence: r.confidence} END) AS entities
                    """,
                    intent_id=intent_id,
                ).single()
            if rec:
                center["name"] = rec.get("title") or center["name"]
                center["region"] = rec.get("region") or center["region"]
                center["amount_wan"] = rec.get("amount_wan") if rec.get("amount_wan") is not None else center["amount_wan"]
                center["dept"] = rec.get("dept") or center["dept"]
                entities = [e for e in (rec.get("entities") or []) if e and e.get("id")]
                if entities:
                    nodes = [{"id": e["id"], "name": e["name"], "type": e["type"], "role": e["role"]} for e in entities]
                    links = [{"source": center["id"], "target": e["id"], "name_zh": e["role"] or "相关于"} for e in entities]
                    return {"success": True, "center": center, "nodes": nodes, "links": links}
    except Exception:  # noqa: BLE001
        pass  # Neo4j 不可用 → 降级 MySQL

    # 2) 降级 MySQL: tender_match 关联实体 + matched_entity
    from app.models.business_network import TenderMatch
    tm_rows = db.execute(
        select(TenderMatch).where(
            TenderMatch.intent_id == intent_id,
            TenderMatch.is_deleted == False,
            TenderMatch.is_expired == False,
        ).order_by(TenderMatch.score.desc()).limit(20)
    ).scalars().all()
    nodes, links = [], []
    seen_ids = set()
    for r in tm_rows:
        nid = f"{'C' if r.entity_type == 'company' else 'P'}{r.entity_id}"
        if nid in seen_ids:
            continue
        seen_ids.add(nid)
        nodes.append({"id": nid, "name": r.entity_name, "type": r.entity_type,
                      "role": r.match_type or "相关于"})
        links.append({"source": center["id"], "target": nid, "name_zh": r.match_type or "相关于"})

    # matched_entity: 业主单位匹配
    me = None
    try:
        me = json.loads(it.matched_entity) if it.matched_entity else None
    except Exception:  # noqa: BLE001
        me = None
    if me and me.get("company_id"):
        nid = f"C{me['company_id']}"
        if nid not in seen_ids:
            nodes.append({"id": nid, "name": me.get("company") or me.get("unit") or "单位",
                          "type": "company", "role": "业主单位"})
            links.append({"source": center["id"], "target": nid, "name_zh": "业主单位"})

    return {"success": True, "center": center, "nodes": nodes, "links": links}


@router.get("/path/{intent_id}")
async def intent_reach_path(
    intent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """意向人脉触达路径(真实): 意向关联实体 → 当前用户(person_id) 的最短人脉链。

    从 Neo4j 查询: 以意向 RELATES_TO 的实体为起点, 经 COLLABORATED_WITH(项目协作)/
    WORKS_AT(任职)/PARTICIPATES_IN(参与项目)/IN_REGION(同地域) 等真实边,
    找到通往「当前登录用户」person_id 的最短路径链。返回触达路径 + 桥接人。

    数据流:
      intent → (RELATES_TO) → target(Company/Person)
      target → ...(协作/任职/项目)... → me(person_id)

    返回: {targets[], paths[{nodes[], rels[]}], bridges[], note}
    """
    it = db.get(IntentNotice, intent_id)
    if not it or it.is_deleted:
        raise HTTPException(status_code=404, detail="意向不存在")
    me_person_id = (user or {}).get("person_id")
    if not me_person_id:
        return {"success": True, "targets": [], "paths": [], "bridges": [],
                "note": "当前账号未关联人员, 无法计算人脉触达路径。请先在后台为账号绑定本人档案。"}

    # 1) 意向关联实体(MySQL tender_match 可靠, 兼容 Neo4j 节点缺失)
    from app.models.business_network import TenderMatch
    tms = db.execute(
        select(TenderMatch).where(
            TenderMatch.intent_id == intent_id,
            TenderMatch.is_deleted == False,
            TenderMatch.is_expired == False,
        ).order_by(TenderMatch.score.desc()).limit(20)
    ).scalars().all()
    targets = [
        {"id": f"{'C' if t.entity_type == 'company' else 'P'}{t.entity_id}",
         "entity_type": t.entity_type, "entity_id": t.entity_id,
         "name": t.entity_name or "", "role": t.match_type or "相关"}
        for t in tms
    ]

    # 2) Neo4j 最短路径查询
    #    强路径: 协作/任职/参与项目(真实人脉边)
    #    弱路径(无强路径时降级): 意向关联单位 WORKS_AT 的人员 → 我的同事 / 同地域行业单位
    paths_out, bridges, note = [], [], ""
    try:
        from app.services import neo4j_sync as _nsync
        driver = _nsync._get_driver()
        if driver is not None:
            with driver.session() as session:
                me_pid = int(me_person_id)
                # ① 强路径: 意向关联实体 → 真实人脉边 → 我
                for tg in targets:
                    ent_key = f"{'company_id' if tg['entity_type'] == 'company' else 'person_id'}"
                    label = "Company" if tg["entity_type"] == "company" else "Person"
                    recs = session.run(
                        """
                        MATCH (s:""" + label + """ {""" + ent_key + """: $sid})
                        MATCH (me:Person {person_id: $mid})
                        MATCH p = shortestPath(
                            (s)-[:COLLABORATED_WITH|WORKS_AT|PARTICIPATES_IN|COLLEAGUE|WINS*1..4]-(me))
                        RETURN [n IN nodes(p) | {type: labels(n)[0], name: n.name,
                               person_id: n.person_id, company_id: n.company_id}] AS nodes,
                               [r IN relationships(p) | type(r)] AS rels,
                               length(p) AS hops
                        ORDER BY hops ASC LIMIT 3
                        """,
                        sid=tg["entity_id"], mid=me_pid,
                    ).values()
                    for rec in recs:
                        ns, rs = rec[0], rec[1]
                        paths_out.append({
                            "target": tg["name"], "target_role": tg["role"],
                            "nodes": ns, "rels": rs, "hops": len(ns) - 1, "kind": "strong",
                        })
                # ② 若无意向关联实体, 补充: 意向发布单位/关联单位 → 单位内人员(WORKS_AT) → 我的同事
                if not paths_out:
                    for tg in targets:
                        if tg["entity_type"] != "company":
                            continue
                        recs = session.run(
                            """
                            MATCH (c:Company {company_id: $sid})
                            MATCH (p:Person)-[:WORKS_AT]->(c)
                            MATCH (me:Person {person_id: $mid})
                            MATCH path = shortestPath(
                                (p)-[:COLLABORATED_WITH|COLLEAGUE|PARTICIPATES_IN*1..3]-(me))
                            RETURN [n IN nodes(path) | {type: labels(n)[0], name: n.name,
                                   person_id: n.person_id, company_id: n.company_id}] AS nodes,
                                   [r IN relationships(path) | type(r)] AS rels,
                                   length(path) AS hops
                            ORDER BY hops ASC LIMIT 3
                            """,
                            sid=tg["entity_id"], mid=me_pid,
                        ).values()
                        for rec in recs:
                            ns, rs = rec[0], rec[1]
                            paths_out.append({
                                "target": tg["name"], "target_role": tg["role"],
                                "nodes": ns, "rels": rs, "hops": len(ns) - 1, "kind": "via_unit",
                            })
                # ③ 仍无路径: 同地域单位降级(IN_REGION 同省, 弱关联提示)
                if not paths_out:
                    for tg in targets:
                        if tg["entity_type"] != "company":
                            continue
                        recs = session.run(
                            """
                            MATCH (c:Company {company_id: $sid})-[:IN_REGION]->(reg:Region)
                            MATCH (my:Person {person_id: $mid})-[:WORKS_AT]->(myc:Company)
                            MATCH (myc)-[:IN_REGION]->(reg)
                            RETURN c.name AS cname, reg.name AS region, myc.name AS myco
                            LIMIT 1
                            """,
                            sid=tg["entity_id"], mid=me_pid,
                        ).values()
                        for rec in recs:
                            if rec:
                                paths_out.append({
                                    "target": tg["name"], "target_role": tg["role"],
                                    "nodes": [
                                        {"type": "Company", "name": rec[0]},
                                        {"type": "Region", "name": rec[1]},
                                        {"type": "Company", "name": rec[2]},
                                    ],
                                    "rels": ["IN_REGION", "IN_REGION"],
                                    "hops": 2, "kind": "weak_region",
                                })
                bridge_names = set()
                for p in paths_out:
                    for nd in p["nodes"][1:-1]:
                        nm = nd.get("name") or ""
                        if nm and nm not in bridge_names:
                            bridge_names.add(nm)
                bridges = [{"name": n} for n in bridge_names]
                if not paths_out:
                    note = "该意向的关联实体与您之间暂无图谱路径，可尝试通过线下人脉或单位业务关联建立联系。"
                else:
                    kinds = {p["kind"] for p in paths_out}
                    if kinds <= {"strong"}:
                        note = f"已找到 {len(paths_out)} 条从意向关联实体到您的真实人脉路径，中间人为可触达的桥接人。"
                    elif "via_unit" in kinds:
                        note = "已找到通过意向关联单位内部人员触达您同事的路径(单位内人员为桥接人)。"
                    else:
                        note = "未找到直接协作路径，已展示同地域弱关联单位(需通过线下业务建立联系)。"
    except Exception as e:  # noqa: BLE001
        note = f"图谱路径查询不可用({str(e)[:60]})，可先查看意向关联实体。"

    paths_out.sort(key=lambda p: p["hops"])
    return {"success": True, "targets": targets, "paths": paths_out,
            "bridges": bridges[:6], "note": note}
