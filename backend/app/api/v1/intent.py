"""意向性信息 API — 政务源意向项目结构化展示/筛选/爬取触发。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.intent_notice import IntentNotice

router = APIRouter(prefix="/intent", tags=["意向信息"])


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
    out = [{
        "id": i.id, "title": i.title, "url": i.url, "dept": i.dept,
        "project_type": i.project_type, "industry": i.industry,
        "amount": float(i.amount) if i.amount is not None else None,
        "region": i.region, "province": i.province, "city": i.city, "county": i.county,
        "contact": i.contact, "published_at": str(i.published_at or ""), "status": i.status,
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
