"""内容工厂 API — 内容生成 / 审核流转 / 渠道 / 统计"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.content import ContentAsset, ContentChannel
from app.services import content_factory

logger = logging.getLogger("api_content")

router = APIRouter(
    prefix="/content",
    tags=["内容工厂"],
    dependencies=[Depends(require_permission("menu_mk_marketing"))],
)


def _asset_dict(a: ContentAsset) -> dict:
    return {
        "id": a.id, "title": a.title, "kind": a.kind, "channel": a.channel or "",
        "channel_name": a.channel_name or "", "summary": a.summary or "", "content": a.content or "",
        "source_data": a.source_data or {}, "status": a.status, "review_comment": a.review_comment or "",
        "published_url": a.published_url or "", "created_by_name": a.created_by_name or "",
        "geo_feedback": a.geo_feedback or {},
        "published_at": a.published_at.strftime("%Y-%m-%d %H:%M") if a.published_at else "",
        "created_at": a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "",
    }


@router.get("/kinds")
async def list_kinds(user: dict = Depends(get_current_user)):
    return {"success": True, "items": [{"value": k, "label": v["label"], "desc": v["desc"]} for k, v in content_factory.KINDS.items()]}


@router.get("/channels")
async def list_channels(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(ContentChannel).where(ContentChannel.is_deleted == False).order_by(ContentChannel.id)).scalars().all()
    return {"success": True, "total": len(rows), "items": [
        {"id": c.id, "name": c.name, "code": c.code, "url_prefix": c.url_prefix or "", "enabled": c.enabled} for c in rows
    ]}


@router.post("/channels/seed")
async def seed_channels(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    content_factory.seed_channels(db)
    rows = db.execute(select(ContentChannel).where(ContentChannel.is_deleted == False)).scalars().all()
    return {"success": True, "total": len(rows)}


@router.get("/assets")
async def list_assets(
    status: Optional[str] = Query(None),
    kind: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(ContentAsset).where(ContentAsset.is_deleted == False)
    if status:
        stmt = stmt.where(ContentAsset.status == status)
    if kind:
        stmt = stmt.where(ContentAsset.kind == kind)
    if keyword:
        stmt = stmt.where(ContentAsset.title.contains(keyword))
    total = len(db.execute(stmt).scalars().all())
    rows = db.execute(
        stmt.order_by(ContentAsset.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return {"success": True, "total": total, "items": [_asset_dict(a) for a in rows]}


@router.get("/assets/{asset_id}")
async def get_asset(asset_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.get(ContentAsset, asset_id)
    if not a or a.is_deleted:
        raise HTTPException(404, "内容不存在")
    return {"success": True, "item": _asset_dict(a)}


@router.get("/assets/{asset_id}/jsonld")
async def get_jsonld(asset_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """生成 Schema.org JSON-LD 结构化标记(可粘贴到官网 <script type=application/ld+json>)。"""
    from app.services import jsonld_builder
    a = db.get(ContentAsset, asset_id)
    if not a or a.is_deleted:
        raise HTTPException(404, "内容不存在")
    try:
        data = jsonld_builder.build_jsonld(db, a)
        pretty = jsonld_builder.build_jsonld_pretty(db, a)
    except Exception as e:  # noqa: BLE001
        logger.exception("jsonld failed")
        raise HTTPException(500, f"JSON-LD 生成失败: {e}") from e
    return {
        "success": True,
        "schema_type": jsonld_builder.KIND_SCHEMA.get(a.kind, "Article"),
        "jsonld": data,
        "pretty": pretty,
        "script_tag": f'<script type="application/ld+json">\n{pretty}\n</script>',
    }


@router.post("/feedback/relink")
async def relink_feedback(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """全量执行「已解析引用 ↔ 已发布内容」回链(闭环反馈)。"""
    from app.services.geo_monitor import link_content_feedback
    linked = link_content_feedback(db)
    return {"success": True, "linked": linked}


@router.delete("/assets/{asset_id}")
async def delete_asset(asset_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.get(ContentAsset, asset_id)
    if not a or a.is_deleted:
        raise HTTPException(404, "内容不存在")
    a.is_deleted = True
    db.commit()
    return {"success": True}


@router.post("/generate")
def generate(body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """生成内容(智能体执行): kind + params → 落库为草稿。

    同步 def: 内部含 LLM 调用(Ollama 最长 240s), 放线程池避免阻塞事件循环。
    """
    kind = (body.get("kind") or "").strip()
    if kind not in content_factory.KINDS:
        raise HTTPException(400, f"kind 无效, 可选: {list(content_factory.KINDS.keys())}")
    try:
        r = content_factory.generate_content(db, kind, body.get("params") or {}, user=user)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        logger.exception("generate failed")
        raise HTTPException(500, f"生成失败: {e}") from e
    return {"success": True, "item": r}


@router.post("/assets/{asset_id}/submit")
async def submit(asset_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        r = content_factory.submit_for_review(db, asset_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"success": True, **r}


@router.post("/assets/{asset_id}/approve")
async def approve(asset_id: int, body: dict = None, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    body = body or {}
    try:
        r = content_factory.approve(db, asset_id, published_url=(body.get("published_url") or "").strip())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"success": True, **r}


@router.post("/assets/{asset_id}/reject")
async def reject(asset_id: int, body: dict = None, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    body = body or {}
    try:
        r = content_factory.reject(db, asset_id, comment=(body.get("comment") or "").strip())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"success": True, **r}


@router.get("/stats")
async def stats(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"success": True, **content_factory.content_stats(db)}
