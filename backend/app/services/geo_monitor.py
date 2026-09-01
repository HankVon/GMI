"""GEO 监测服务 — 把 AI 引擎变成第 N 个数据源。

设计:
  - 三种采集适配器:
    manual    用户手动粘贴 AI 回答(最稳, 无需反爬/密钥, 兜底可用)
    crawl4ai  用本地 crawl4ai 抓取引擎网页(engine.url 支持 {kw} 占位)
    openai_api 调 OpenAI 兼容 chat/completions 接口(豆包/DeepSeek/硅基流动等)
  - LLM 解析: 对回答做 引用来源/提及实体/品牌可见性/一句话总结 抽取(Ollama)。
  - 品牌词: mk_config.brand_names(JSON数组), 匹配回答中是否提及本公司。
"""
import json
import logging
import re
import time
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.llm_enhance import LLMUnavailable, _extract_json, _generate

logger = logging.getLogger("geo_monitor")

# 引擎适配器说明(供前端展示)
ADAPTERS = {
    "manual": "手动粘贴(最稳)",
    "crawl4ai": "crawl4ai 网页抓取",
    "openai_api": "OpenAI 兼容 API",
}


# ── 营销配置 ──────────────────────────────────────────────

def get_config(db: Session, key: str, default: str = "") -> str:
    """读取营销配置(JSON字符串)。"""
    from app.models.geo import MkConfig
    row = db.execute(select(MkConfig).where(MkConfig.cfg_key == key)).scalar_one_or_none()
    return row.cfg_value if row and row.cfg_value else default


def set_config(db: Session, key: str, value: str, description: str = "") -> None:
    """写入营销配置(upsert)。"""
    from app.models.geo import MkConfig
    row = db.execute(select(MkConfig).where(MkConfig.cfg_key == key)).scalar_one_or_none()
    if row:
        row.cfg_value = value
    else:
        db.add(MkConfig(cfg_key=key, cfg_value=value, description=description))
    db.commit()


def get_config_json(db: Session, key: str, default: list = None) -> list:
    """读取 JSON 数组配置。"""
    raw = get_config(db, key, "")
    if not raw:
        return default or []
    try:
        val = json.loads(raw)
        return val if isinstance(val, list) else (default or [])
    except Exception:  # noqa: BLE001
        return default or []


def get_brand_names(db: Session) -> list:
    """品牌词列表(本公司名称/简称), 用于 AI 回答中的可见性匹配。"""
    return get_config_json(db, "brand_names")


def get_industry_keywords(db: Session) -> list:
    """行业关键词(内容选题/商机评分用)。"""
    return get_config_json(db, "industry_keywords")


def get_agent_model(db: Session) -> str:
    """营销智能体使用的 Ollama 模型(可在前端配置, 缺省用 settings.OLLAMA_MODEL)。"""
    from app.config import settings
    m = get_config(db, "llm_model", "").strip()
    return m or settings.OLLAMA_MODEL


# ── 采集适配器 ────────────────────────────────────────────

def _fetch_openai_api(engine, keyword: str) -> dict:
    """调用 OpenAI 兼容 chat/completions, 返回 {answer, raw, citations}。"""
    import httpx
    endpoint = engine.api_endpoint or ""
    api_key = engine.api_key or ""
    model = engine.api_model or "gpt-4o-mini"
    if not endpoint:
        raise ValueError("openai_api 适配器未配置 api_endpoint")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": keyword}],
        "temperature": 0.3,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    # 本地 Ollama 大模型单条生成可达 2 分钟(实测 117s), 120s 硬超时会误杀慢查询; 放宽到 300s
    resp = httpx.post(endpoint, json=payload, headers=headers, timeout=300.0)
    resp.raise_for_status()
    data = resp.json()
    answer = ""
    try:
        answer = data["choices"][0]["message"]["content"] or ""
    except Exception:  # noqa: BLE001
        answer = json.dumps(data, ensure_ascii=False)[:20000]
    # 兼容部分引擎返回 citations/urls 字段
    citations = []
    for k in ("citations", "urls", "sources"):
        raw = data.get(k) or []
        if isinstance(raw, list):
            for c in raw:
                if isinstance(c, str):
                    citations.append({"title": c, "url": c, "domain": _domain_of(c)})
                elif isinstance(c, dict):
                    u = c.get("url") or c.get("link") or ""
                    citations.append({
                        "title": c.get("title") or u, "url": u,
                        "domain": _domain_of(u) if u else "",
                    })
    return {"answer": answer, "raw": json.dumps(data, ensure_ascii=False)[:50000], "citations": citations}


def get_geo_crawl_config(db: Session) -> dict:
    """GEO 交互式抓取配置(mk_config.geo_crawl): 引擎code -> 参数段。

    段字段:
      url_template   查询 URL 模板({kw} 占位), 缺省用 engine.url
      input_selector 搜索输入框选择器(提供后模拟 点击->输入->回车)
      selector       回答容器选择器(提供后只抽该容器文本)
      wait_for       CSS 选择器, 等待回答渲染
      page_timeout   页加载超时毫秒(默认 180000)
      extra_delay    等待后额外停留秒数(默认 2)
      cookies       登录 cookie: Playwright 数组 [{name,value,domain,path}] 或 'a=b; c=d' 字符串(直接粘 cURL cookie 头)
      login_markers  登录墙特征词(默认 ["登录","请登录"]), 命中回答容器检查则报错提示
      min_answer_chars 回答容器最小文本长度(默认 150), 更短视为未渲染出回答
    """
    raw = get_config(db, "geo_crawl", "")
    if not raw:
        return {}
    try:
        cfg = json.loads(raw)
        return cfg if isinstance(cfg, dict) else {}
    except Exception:  # noqa: BLE001
        logger.warning("[geo] geo_crawl 配置非合法 JSON, 忽略")
        return {}


def _fetch_crawl4ai(engine, keyword: str, crawl_cfg: dict = None) -> dict:
    """用 crawl4ai 交互式抓取 AI 引擎网页(url 支持 {kw} 占位)。"""
    from app.services.crawl4ai_client import Crawl4aiError, crawl4ai_client
    cfg = crawl_cfg or {}
    url = (cfg.get("url_template") or engine.url or "").replace("{kw}", keyword)
    if not url:
        raise ValueError("crawl4ai 适配器未配置 url 或 geo_crawl.url_template")
    try:
        r = crawl4ai_client.scrape(
            url,
            page_timeout=int(cfg.get("page_timeout") or 180000),
            wait_for=cfg.get("wait_for") or None,
            cookies=cfg.get("cookies") or None,
            selector=cfg.get("selector") or None,
            extra_delay=float(cfg.get("extra_delay") or 2.0),
            query_text=cfg.get("query_text") or keyword,
            input_selector=cfg.get("input_selector") or None,
        )
    except Crawl4aiError as e:
        raise ValueError(f"crawl4ai 抓取失败: {e}") from e
    md = (r.get("markdown") or "").strip()
    if not md:
        raise ValueError("crawl4ai 未返回正文(可能被反爬拦截)")
    # 登录墙/未命中启发式: 配置了回答容器却只抓到导航或落地页(含登录字眼 或 文本过短)
    if cfg.get("selector"):
        markers = cfg.get("login_markers") or ["登录", "请登录"]
        head = md[:300]
        min_chars = int(cfg.get("min_answer_chars") or 150)
        if any(mk in head for mk in markers) or len(md) < min_chars:
            raise ValueError(
                "抓取未命中回答容器(疑似登录墙或回答未渲染): 请配置该引擎的登录 cookie "
                "(PUT /api/v1/geo/config 的 geo_crawl.<code>.cookies)"
            )
    return {"answer": md[:20000], "raw": md[:50000], "citations": []}


def fetch_engine_answer(engine, keyword: str, crawl_cfg: dict = None) -> dict:
    """按引擎适配器采集回答。返回 {answer, raw, citations, adapter}。

    crawl_cfg: crawl4ai 引擎的交互式抓取配置(见 get_geo_crawl_config)。
    """
    adapter = engine.adapter or "manual"
    if adapter == "openai_api":
        r = _fetch_openai_api(engine, keyword)
    elif adapter == "crawl4ai":
        r = _fetch_crawl4ai(engine, keyword, crawl_cfg=crawl_cfg)
    elif adapter == "manual":
        raise ValueError("manual 适配器不支持自动采集, 请手动粘贴回答")
    else:
        raise ValueError(f"未知适配器: {adapter}")
    r["adapter"] = adapter
    return r


# ── LLM 解析 ──────────────────────────────────────────────

def _domain_of(url: str) -> str:
    if not url:
        return ""
    m = re.search(r"https?://([^/]+)", url)
    if m:
        return m.group(1).replace("www.", "")
    m2 = re.search(r"([a-z0-9-]+(?:\.[a-z0-9-]+)+)", url.lower())
    return m2.group(1) if m2 else ""


def parse_answer_with_llm(db: Session, answer_text: str, keyword: str, brand_names: list) -> dict:
    """LLM 解析 AI 回答: 引用来源/提及实体/品牌可见性/总结。

    返回 {cited_sources, mentioned_entities, brand_hits, self_visible, self_rank, summary}
    Ollama 不可用时降级: 用正则抽 URL + 品牌词直接匹配, 保证可用。
    """
    result = {
        "cited_sources": [], "mentioned_entities": [], "brand_hits": [],
        "self_visible": False, "self_rank": 0, "summary": "",
    }
    if not answer_text:
        return result

    brands = [b for b in (brand_names or []) if b]
    prompt = (
        "你是 GEO(生成式引擎优化)分析师。以下是 AI 搜索引擎对问题【" + keyword + "】的回答全文。\n"
        "请抽取: 1) 回答中提到的公司/单位名称(实体, 标注类型 company 或 org); "
        "2) 回答中出现的引用来源(网址/站点名); 3) 一句话总结这个回答在推荐什么。\n"
        "只输出 JSON, 格式: {\"entities\": [{\"name\": \"公司名\", \"type\": \"company\"}], "
        "\"sources\": [{\"title\": \"标题或URL\", \"url\": \"\"}], \"summary\": \"一句话\"}\n"
        "没有则给空数组/空字符串。不要编造。\n\n回答全文:\n" + answer_text[:8000]
    )
    parsed = {}
    try:
        out = _generate(prompt, timeout=180, model=get_agent_model(db))
        parsed = _extract_json(out) or {}
    except LLMUnavailable:
        logger.warning("ollama 不可用, GEO 解析降级为正则+品牌匹配")
    except Exception as e:  # noqa: BLE001
        logger.warning("GEO 解析异常: %s", e)

    # 实体
    entities = parsed.get("entities") or []
    if not isinstance(entities, list):
        entities = []
    seen = set()
    mentioned = []
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        name = str(ent.get("name") or "").strip()
        etype = str(ent.get("type") or "company").strip()
        if not name or len(name) < 2 or name.lower() in seen:
            continue
        seen.add(name.lower())
        mentioned.append({"name": name, "type": etype})
    if not mentioned:
        # 降级: 正则抽中文单位词(粗粒度)
        for m in re.finditer(r"([\u4e00-\u9fa5]{2,20}(?:公司|集团|研究院|设计院|局|所|中心|大学))", answer_text):
            n = m.group(1)
            if n.lower() not in seen:
                seen.add(n.lower())
                mentioned.append({"name": n, "type": "company"})
                if len(mentioned) >= 20:
                    break
    result["mentioned_entities"] = mentioned[:50]

    # 引用来源
    sources = parsed.get("sources") or []
    if not isinstance(sources, list):
        sources = []
    cited = []
    for s in sources:
        if not isinstance(s, dict):
            continue
        url = str(s.get("url") or "").strip()
        title = str(s.get("title") or url or "").strip()
        if not url and not title:
            continue
        cited.append({"title": title[:200], "url": url[:500], "domain": _domain_of(url)})
    # 正则兜底: 总是补抓回答中的 URL(LLM 可能漏掉, 引用回链依赖完整来源)
    for m in re.finditer(r"https?://[^\s\])}，。；、]+", answer_text):
        u = m.group(0).rstrip(".,;:!?")
        if len(u) > 6:
            cited.append({"title": u[:200], "url": u[:500], "domain": _domain_of(u)})
    # 去重(URL 优先, title 兜底)
    seen_u = set()
    unique = []
    for c in cited:
        k = c["url"] or c["title"]
        if k and k not in seen_u:
            seen_u.add(k)
            unique.append(c)
    cited = unique
    result["cited_sources"] = cited[:50]

    # 品牌可见性: 品牌词匹配(全名优先, 再子串)
    hits = []
    text_low = answer_text
    for i, b in enumerate(brands, 1):
        if b and b in text_low:
            hits.append({"name": b, "position": i})
    result["brand_hits"] = hits
    result["self_visible"] = bool(hits)
    result["self_rank"] = hits[0]["position"] if hits else 0

    # 总结
    summary = str(parsed.get("summary") or "").strip()
    result["summary"] = (summary or answer_text.strip()[:200])[:500]
    return result


# ── 记录与执行 ────────────────────────────────────────────

def record_manual_mention(db: Session, engine_id: Optional[int], keyword: str,
                          answer_text: str, raw_text: str = "") -> dict:
    """手动粘贴回答: 创建 mention 并立即 LLM 解析。"""
    from app.models.geo import GeoEngine, GeoMention
    engine = None
    if engine_id:
        engine = db.get(GeoEngine, engine_id)
    engine_name = engine.name if engine else "手动"
    mention = GeoMention(
        engine_id=engine.id if engine else None,
        engine_name=engine_name,
        keyword=keyword,
        keyword_id=None,
        asked_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        adapter="manual",
        answer_text=answer_text,
        raw_text=raw_text or answer_text,
        status="pending",
    )
    db.add(mention)
    db.commit()
    db.refresh(mention)
    _parse_and_save(db, mention)
    return {"id": mention.id, "engine": engine_name, "keyword": keyword}


def _parse_and_save(db: Session, mention) -> None:
    """对一条 mention 做 LLM 解析并落库(失败标记 error 不阻断)。"""
    from app.models.geo import GeoMention
    brand_names = get_brand_names(db)
    try:
        parsed = parse_answer_with_llm(db, mention.answer_text or "", mention.keyword, brand_names)
        mention.cited_sources = parsed["cited_sources"]
        mention.mentioned_entities = parsed["mentioned_entities"]
        mention.brand_hits = parsed["brand_hits"]
        mention.self_visible = parsed["self_visible"]
        mention.self_rank = parsed["self_rank"]
        mention.summary = parsed["summary"]
        mention.status = "parsed"
        mention.error = None
    except Exception as e:  # noqa: BLE001
        logger.warning("[geo] mention %s 解析失败: %s", mention.id, e)
        mention.status = "error"
        mention.error = str(e)[:500]
    db.commit()
    # 闭环反馈: 解析完成后立即做「引用来源 ↔ 已发布内容」回链
    try:
        link_content_feedback(db, mention=mention)
    except Exception as e:  # noqa: BLE001
        logger.warning("[geo] 内容反馈回链失败: %s", e)


def link_content_feedback(db: Session, mention=None) -> int:
    """闭环反馈: 把已解析 mention 的引用来源与已发布内容做域名匹配回链。

    命中 → 在 content_asset.geo_feedback 记录 mention_ids/cite_count/last_cited_at,
    形成「发布内容 → AI 引用 → 效果回流」闭环。
    mention 为空时全量扫描(供手动 relink 接口调用)。
    """
    from app.models.geo import GeoMention
    from app.models.content import ContentAsset

    if mention is not None:
        mentions = [mention] if mention.status == "parsed" else []
    else:
        mentions = db.execute(
            select(GeoMention).where(GeoMention.is_deleted == False, GeoMention.status == "parsed")
        ).scalars().all()
    if not mentions:
        return 0
    published = db.execute(
        select(ContentAsset).where(ContentAsset.is_deleted == False, ContentAsset.status == "published")
    ).scalars().all()
    if not published:
        return 0
    linked = 0
    for m in mentions:
        for s in (m.cited_sources or []):
            dom = s.get("domain") or ""
            if not dom:
                continue
            for a in published:
                purl = (a.published_url or "").lower()
                if not purl or dom not in purl:
                    continue
                fb = dict(a.geo_feedback or {})
                ids = list(fb.get("mention_ids") or [])
                if m.id not in ids:
                    ids.append(m.id)
                    fb["mention_ids"] = ids
                    fb["cite_count"] = len(ids)
                    fb["last_cited_at"] = m.asked_at.strftime("%Y-%m-%d %H:%M") if m.asked_at else ""
                    a.geo_feedback = fb
                    linked += 1
    if linked:
        db.commit()
    return linked


def test_engine(engine) -> dict:
    """引擎连通性测试(前端按钮触发, 不落库)。"""
    adapter = engine.adapter or "manual"
    if adapter == "openai_api":
        try:
            r = _fetch_openai_api(engine, "你好, 请只回复四个字: 连接正常")
            answer = (r.get("answer") or "")[:100]
            return {"ok": True, "detail": f"API 连通, 模型回复: {answer}"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "detail": f"API 调用失败: {e}"}
    if adapter == "crawl4ai":
        from app.services.crawl4ai_client import Crawl4aiError, crawl4ai_client
        try:
            crawl4ai_client.scrape(engine.url or "https://example.com")
            return {"ok": True, "detail": "crawl4ai 服务可达"}
        except Crawl4aiError as e:
            return {"ok": False, "detail": f"crawl4ai 不可达: {e}"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "detail": f"crawl4ai 异常: {e}"}
    return {"ok": True, "detail": "manual 适配器无需测试(手动粘贴回答即可)"}


def run_keyword_on_engine(db: Session, keyword_id: int, engine_id: int) -> dict:
    """对 关键词×引擎 执行一次 采集→解析→落库。"""
    from app.models.geo import GeoEngine, GeoKeyword, GeoMention
    kw = db.get(GeoKeyword, keyword_id)
    engine = db.get(GeoEngine, engine_id)
    if not kw or not engine:
        return {"ok": False, "error": "keyword/engine 不存在"}
    t0 = time.time()
    mention = GeoMention(
        engine_id=engine.id, engine_name=engine.name, keyword_id=kw.id, keyword=kw.keyword,
        asked_at=time.strftime("%Y-%m-%d %H:%M:%S"), adapter=engine.adapter, status="pending",
    )
    db.add(mention)
    db.commit()
    db.refresh(mention)
    try:
        crawl_cfg = {}
        if engine.adapter == "crawl4ai":
            crawl_cfg = get_geo_crawl_config(db).get(engine.code) or {}
        fetched = fetch_engine_answer(engine, kw.keyword, crawl_cfg=crawl_cfg)
        mention.answer_text = fetched["answer"]
        mention.raw_text = fetched["raw"]
        if fetched.get("citations"):
            mention.cited_sources = fetched["citations"]
        db.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("[geo] 采集失败 kw=%s engine=%s: %s", kw.keyword, engine.name, e)
        mention.status = "error"
        mention.error = str(e)[:500]
        mention.elapsed_ms = int((time.time() - t0) * 1000)
        db.commit()
        return {"ok": False, "id": mention.id, "error": str(e)[:300]}
    # 已有 citations 时, LLM 解析跳过 sources(回答里没有 URL 时保留 API citations)
    _parse_and_save(db, mention)
    mention.elapsed_ms = int((time.time() - t0) * 1000)
    db.commit()
    kw.last_run_at = time.strftime("%Y-%m-%d %H:%M:%S")
    db.commit()
    return {"ok": True, "id": mention.id, "engine": engine.name, "keyword": kw.keyword}


def run_all_enabled(db: Session, limit_per_engine: int = 20) -> dict:
    """定时任务入口: 遍历启用关键词 × 绑定引擎, 逐个执行(手动适配器跳过)。

    返回 {total, ok, failed, skipped, results}
    """
    from app.models.geo import GeoEngine, GeoKeyword
    keywords = db.execute(
        select(GeoKeyword).where(GeoKeyword.is_deleted == False, GeoKeyword.enabled == True)
    ).scalars().all()
    engines = db.execute(
        select(GeoEngine).where(GeoEngine.is_deleted == False, GeoEngine.enabled == True)
    ).scalars().all()
    results = []
    ok = failed = skipped = 0
    for kw in keywords:
        bound = []
        if kw.engines:
            try:
                codes = json.loads(kw.engines)
            except Exception:  # noqa: BLE001
                codes = []
            bound = [e for e in engines if e.code in codes]
        else:
            bound = list(engines)
        for engine in bound:
            if engine.adapter == "manual":
                skipped += 1
                continue
            try:
                r = run_keyword_on_engine(db, kw.id, engine.id)
                results.append(r)
                ok += 1 if r.get("ok") else 0
                failed += 0 if r.get("ok") else 1
            except Exception as e:  # noqa: BLE001
                logger.warning("[geo] run failed kw=%s engine=%s: %s", kw.keyword, engine.name, e)
                failed += 1
            if ok + failed >= limit_per_engine:
                break
        if ok + failed >= limit_per_engine:
            break
    return {"total": ok + failed, "ok": ok, "failed": failed, "skipped": skipped, "results": results[:50]}


# ── 看板统计 ──────────────────────────────────────────────

def dashboard_stats(db: Session, days: int = 30) -> dict:
    """GEO 监测看板: 可见性/引擎对比/高频引用源/高频提及公司/趋势。"""
    from app.models.geo import GeoEngine, GeoMention
    from datetime import datetime, timedelta

    cutoff = datetime.now() - timedelta(days=days)
    mentions = db.execute(
        select(GeoMention).where(
            GeoMention.is_deleted == False, GeoMention.asked_at >= cutoff,
            GeoMention.status != "error",
        )
    ).scalars().all()

    total = len(mentions)
    self_visible = [m for m in mentions if m.self_visible]
    visible_count = len(self_visible)

    # 引擎维度
    engines = db.execute(select(GeoEngine).where(GeoEngine.is_deleted == False)).scalars().all()
    engine_rows = []
    for e in engines:
        em = [m for m in mentions if m.engine_id == e.id]
        ev = [m for m in em if m.self_visible]
        engine_rows.append({
            "id": e.id, "name": e.name, "code": e.code, "adapter": e.adapter, "enabled": e.enabled,
            "mentions": len(em), "visible": len(ev), "visible_ratio": round(len(ev) / len(em), 2) if em else 0,
        })

    # 引用来源榜
    src_counter: dict = {}
    for m in mentions:
        for s in (m.cited_sources or []):
            key = s.get("domain") or s.get("title") or ""
            if not key:
                continue
            item = src_counter.setdefault(key, {"domain": key, "title": s.get("title") or key, "count": 0, "urls": set()})
            item["count"] += 1
            if s.get("url"):
                item["urls"].add(s["url"])
    cited_sources = sorted(
        [{"domain": v["domain"], "title": v["title"], "count": v["count"], "urls": list(v["urls"])[:3]} for v in src_counter.values()],
        key=lambda x: -x["count"],
    )[:20]

    # 提及公司榜
    ent_counter: dict = {}
    for m in mentions:
        for ent in (m.mentioned_entities or []):
            name = str(ent.get("name") or "").strip()
            if not name:
                continue
            ent_counter[name] = ent_counter.get(name, 0) + 1
    mentioned_top = sorted(
        [{"name": k, "count": v} for k, v in ent_counter.items()], key=lambda x: -x["count"],
    )[:20]

    # 趋势(按天)
    trend_map: dict = {}
    for m in mentions:
        day = m.asked_at.strftime("%m-%d")
        t = trend_map.setdefault(day, {"date": day, "total": 0, "visible": 0})
        t["total"] += 1
        if m.self_visible:
            t["visible"] += 1
    trend = sorted(trend_map.values(), key=lambda x: x["date"])

    return {
        "days": days, "total_mentions": total, "visible_count": visible_count,
        "visible_ratio": round(visible_count / total, 2) if total else 0,
        "engines": engine_rows, "cited_sources": cited_sources, "mentioned_top": mentioned_top,
        "trend": trend,
    }
