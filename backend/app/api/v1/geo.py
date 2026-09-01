"""GEO 监测 API — AI 引擎配置 / 关键词任务 / 查询结果 / 可见性看板"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.middleware.auth import get_current_user, require_permission
from app.models.geo import GeoEngine, GeoKeyword, GeoMention
from app.services import geo_monitor

logger = logging.getLogger("api_geo")

router = APIRouter(
    prefix="/geo",
    tags=["GEO监测"],
    dependencies=[Depends(require_permission("menu_mk_marketing"))],
)


# ── 引擎配置 ──────────────────────────────────────────────

def _engine_dict(e: GeoEngine) -> dict:
    return {
        "id": e.id, "name": e.name, "code": e.code, "url": e.url or "",
        "adapter": e.adapter, "api_endpoint": e.api_endpoint or "", "api_model": e.api_model or "",
        "has_api_key": bool(e.api_key), "notes": e.notes or "", "enabled": e.enabled,
        "created_at": e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else "",
    }


@router.get("/adapters")
async def list_adapters(user: dict = Depends(get_current_user)):
    return {"success": True, "items": [{"value": k, "label": v} for k, v in geo_monitor.ADAPTERS.items()]}


@router.get("/engines")
async def list_engines(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(GeoEngine).where(GeoEngine.is_deleted == False).order_by(GeoEngine.id)).scalars().all()
    return {"success": True, "total": len(rows), "items": [_engine_dict(e) for e in rows]}


@router.post("/engines")
async def create_engine(body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    name = (body.get("name") or "").strip()
    code = (body.get("code") or "").strip()
    if not name or not code:
        raise HTTPException(400, "name/code 必填")
    exists = db.execute(select(GeoEngine).where(GeoEngine.code == code, GeoEngine.is_deleted == False)).scalar_one_or_none()
    if exists:
        raise HTTPException(400, f"引擎编码 {code} 已存在")
    e = GeoEngine(
        name=name, code=code, url=(body.get("url") or "").strip() or None,
        adapter=(body.get("adapter") or "manual").strip(),
        api_endpoint=(body.get("api_endpoint") or "").strip() or None,
        api_key=(body.get("api_key") or "").strip() or None,
        api_model=(body.get("api_model") or "").strip() or None,
        notes=(body.get("notes") or "").strip() or None,
        enabled=bool(body.get("enabled", True)),
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return {"success": True, "item": _engine_dict(e)}


@router.put("/engines/{engine_id}")
async def update_engine(engine_id: int, body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    e = db.get(GeoEngine, engine_id)
    if not e or e.is_deleted:
        raise HTTPException(404, "引擎不存在")
    if "name" in body:
        e.name = str(body["name"]).strip() or e.name
    if "url" in body:
        e.url = (body["url"] or "").strip() or None
    if "adapter" in body:
        e.adapter = str(body["adapter"]).strip()
    if "api_endpoint" in body:
        e.api_endpoint = (body["api_endpoint"] or "").strip() or None
    if "api_key" in body:
        e.api_key = (body["api_key"] or "").strip() or None
    if "api_model" in body:
        e.api_model = (body["api_model"] or "").strip() or None
    if "notes" in body:
        e.notes = (body["notes"] or "").strip() or None
    if "enabled" in body:
        e.enabled = bool(body["enabled"])
    db.commit()
    db.refresh(e)
    return {"success": True, "item": _engine_dict(e)}


@router.delete("/engines/{engine_id}")
async def delete_engine(engine_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    e = db.get(GeoEngine, engine_id)
    if not e or e.is_deleted:
        raise HTTPException(404, "引擎不存在")
    e.is_deleted = True
    db.commit()
    return {"success": True}


@router.post("/engines/{engine_id}/test")
def test_engine(engine_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """引擎连通性测试(openai_api 发一条消息; crawl4ai 探测服务; manual 直接提示)。

    同步 def: 内部含网络调用, 由 FastAPI 丢到线程池执行, 避免阻塞事件循环。
    """
    e = db.get(GeoEngine, engine_id)
    if not e or e.is_deleted:
        raise HTTPException(404, "引擎不存在")
    r = geo_monitor.test_engine(e)
    return {"success": r["ok"], **r}


# ── 关键词任务 ────────────────────────────────────────────

def _keyword_dict(k: GeoKeyword) -> dict:
    return {
        "id": k.id, "keyword": k.keyword, "region": k.region or "", "category": k.category or "",
        "engines": k.engines or "", "priority": k.priority, "enabled": k.enabled,
        "last_run_at": k.last_run_at.strftime("%Y-%m-%d %H:%M") if k.last_run_at else "",
        "created_at": k.created_at.strftime("%Y-%m-%d %H:%M") if k.created_at else "",
    }


@router.get("/keywords")
async def list_keywords(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(GeoKeyword).where(GeoKeyword.is_deleted == False).order_by(GeoKeyword.priority.desc(), GeoKeyword.id)).scalars().all()
    return {"success": True, "total": len(rows), "items": [_keyword_dict(k) for k in rows]}


@router.post("/keywords")
async def create_keyword(body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    kw = (body.get("keyword") or "").strip()
    if not kw:
        raise HTTPException(400, "keyword 必填")
    engines = body.get("engines")
    k = GeoKeyword(
        keyword=kw,
        region=(body.get("region") or "").strip() or None,
        category=(body.get("category") or "").strip() or None,
        engines=json.dumps(engines, ensure_ascii=False) if isinstance(engines, list) and engines else None,
        priority=int(body.get("priority") or 5),
        enabled=bool(body.get("enabled", True)),
    )
    db.add(k)
    db.commit()
    db.refresh(k)
    return {"success": True, "item": _keyword_dict(k)}


@router.put("/keywords/{keyword_id}")
async def update_keyword(keyword_id: int, body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    k = db.get(GeoKeyword, keyword_id)
    if not k or k.is_deleted:
        raise HTTPException(404, "关键词任务不存在")
    if "keyword" in body and str(body.get("keyword") or "").strip():
        k.keyword = str(body["keyword"]).strip()
    if "region" in body:
        k.region = (body["region"] or "").strip() or None
    if "category" in body:
        k.category = (body["category"] or "").strip() or None
    if "engines" in body:
        engines = body["engines"]
        k.engines = json.dumps(engines, ensure_ascii=False) if isinstance(engines, list) and engines else None
    if "priority" in body:
        k.priority = int(body["priority"])
    if "enabled" in body:
        k.enabled = bool(body["enabled"])
    db.commit()
    db.refresh(k)
    return {"success": True, "item": _keyword_dict(k)}


@router.delete("/keywords/{keyword_id}")
async def delete_keyword(keyword_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    k = db.get(GeoKeyword, keyword_id)
    if not k or k.is_deleted:
        raise HTTPException(404, "关键词任务不存在")
    k.is_deleted = True
    db.commit()
    return {"success": True}


# ── 查询结果 ──────────────────────────────────────────────

def _mention_dict(m: GeoMention) -> dict:
    return {
        "id": m.id, "engine_id": m.engine_id, "engine_name": m.engine_name or "",
        "keyword_id": m.keyword_id, "keyword": m.keyword, "asked_at": m.asked_at.strftime("%Y-%m-%d %H:%M") if m.asked_at else "",
        "adapter": m.adapter, "answer_text": m.answer_text or "", "raw_text": m.raw_text or "",
        "cited_sources": m.cited_sources or [], "mentioned_entities": m.mentioned_entities or [],
        "brand_hits": m.brand_hits or [], "self_visible": bool(m.self_visible), "self_rank": m.self_rank or 0,
        "summary": m.summary or "", "status": m.status, "error": m.error or "", "elapsed_ms": m.elapsed_ms,
        "created_at": m.created_at.strftime("%Y-%m-%d %H:%M") if m.created_at else "",
    }


@router.get("/mentions")
async def list_mentions(
    engine_id: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    self_visible: Optional[bool] = Query(None),
    days: int = Query(30, ge=1, le=3650),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(GeoMention).where(GeoMention.is_deleted == False)
    if engine_id:
        stmt = stmt.where(GeoMention.engine_id == engine_id)
    if keyword:
        stmt = stmt.where(GeoMention.keyword.contains(keyword))
    if status:
        stmt = stmt.where(GeoMention.status == status)
    if self_visible is not None:
        stmt = stmt.where(GeoMention.self_visible == self_visible)
    if days:
        cutoff = datetime.now() - timedelta(days=days)
        stmt = stmt.where(GeoMention.asked_at >= cutoff)
    total = len(db.execute(stmt).scalars().all())
    rows = db.execute(
        stmt.order_by(GeoMention.asked_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return {"success": True, "total": total, "items": [_mention_dict(m) for m in rows]}


@router.post("/mentions/manual")
def create_manual_mention(body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """手动粘贴 AI 回答(适配器兜底): 记录并立即 LLM 解析。

    同步 def: 解析含 LLM 调用(Ollama 可达 180s), 放线程池避免阻塞事件循环。
    """
    answer = (body.get("answer_text") or "").strip()
    keyword = (body.get("keyword") or "").strip()
    if not answer or not keyword:
        raise HTTPException(400, "answer_text 与 keyword 必填")
    try:
        r = geo_monitor.record_manual_mention(
            db, engine_id=body.get("engine_id"), keyword=keyword,
            answer_text=answer, raw_text=(body.get("raw_text") or "").strip(),
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("manual mention failed")
        raise HTTPException(500, f"记录失败: {e}") from e
    mention = db.get(GeoMention, r["id"])
    return {"success": True, "item": _mention_dict(mention)}


@router.post("/mentions/fetch")
def fetch_mentions(body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """触发采集: 传 keyword_id+engine_id 执行单个; 不传则跑全部启用任务。

    同步 def: 内部串行跑 crawl4ai/Ollama 网络调用(单个最长 300-600s),
    放线程池执行, 避免阻塞事件循环导致全站无响应。
    """
    keyword_id = body.get("keyword_id")
    engine_id = body.get("engine_id")
    if keyword_id and engine_id:
        r = geo_monitor.run_keyword_on_engine(db, int(keyword_id), int(engine_id))
        return {"success": bool(r.get("ok")), **r}
    result = geo_monitor.run_all_enabled(db, limit_per_engine=int(body.get("limit") or 20))
    return {"success": True, **result}


@router.post("/mentions/{mention_id}/reparse")
def reparse_mention(mention_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """重新 LLM 解析一条 mention(同步 def, 防阻塞事件循环)。"""
    m = db.get(GeoMention, mention_id)
    if not m or m.is_deleted:
        raise HTTPException(404, "记录不存在")
    geo_monitor._parse_and_save(db, m)
    db.refresh(m)
    return {"success": True, "item": _mention_dict(m)}


@router.delete("/mentions/{mention_id}")
async def delete_mention(mention_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.get(GeoMention, mention_id)
    if not m or m.is_deleted:
        raise HTTPException(404, "记录不存在")
    m.is_deleted = True
    db.commit()
    return {"success": True}


# ── 看板与配置 ────────────────────────────────────────────

@router.get("/dashboard")
async def geo_dashboard(days: int = Query(30, ge=1, le=365), user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"success": True, **geo_monitor.dashboard_stats(db, days=days)}


@router.get("/config")
async def get_config(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        "success": True,
        "brand_names": geo_monitor.get_brand_names(db),
        "industry_keywords": geo_monitor.get_industry_keywords(db),
        "llm_model": geo_monitor.get_agent_model(db),
        "default_llm_model": settings.OLLAMA_MODEL,
        "geo_crawl": geo_monitor.get_geo_crawl_config(db),
    }


@router.put("/config")
async def update_config(body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    if "brand_names" in body:
        geo_monitor.set_config(db, "brand_names", json.dumps(body["brand_names"], ensure_ascii=False), "本公司品牌词")
    if "industry_keywords" in body:
        geo_monitor.set_config(db, "industry_keywords", json.dumps(body["industry_keywords"], ensure_ascii=False), "行业关键词")
    if "llm_model" in body and str(body.get("llm_model") or "").strip():
        geo_monitor.set_config(db, "llm_model", str(body["llm_model"]).strip(), "营销智能体 LLM 模型")
    if "geo_crawl" in body and isinstance(body["geo_crawl"], dict):
        geo_monitor.set_config(db, "geo_crawl", json.dumps(body["geo_crawl"], ensure_ascii=False),
                               "GEO 交互式抓取配置(引擎code->参数: url_template/input_selector/selector/cookies等)")
    return {"success": True, "brand_names": geo_monitor.get_brand_names(db),
            "industry_keywords": geo_monitor.get_industry_keywords(db),
            "llm_model": geo_monitor.get_agent_model(db),
            "geo_crawl": geo_monitor.get_geo_crawl_config(db)}
