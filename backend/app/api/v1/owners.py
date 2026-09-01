"""业主概览看板 / 业主专查检索接口。"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.owner import Owner
from app.models.opportunity import Opportunity

router = APIRouter(prefix="/owners", tags=["业主概览/专查"])


@router.get("/overview")
async def owner_overview(db: Session = Depends(get_db),
                          user: dict = Depends(get_current_user)):
    """业主维度聚合看板: 类型分布 + 规模分布 + 行业 Top + 累计投资。"""
    by_type_rows = db.execute(
        select(Owner.owner_type, func.count(Owner.id), func.coalesce(func.sum(Owner.total_amount_wan), 0))
        .where(Owner.is_deleted == 0).group_by(Owner.owner_type)
    ).all()
    by_scale_rows = db.execute(
        select(Owner.owner_scale, func.count(Owner.id))
        .where(Owner.is_deleted == 0).group_by(Owner.owner_scale)
    ).all()
    by_industry_rows = db.execute(
        select(Owner.industry, func.count(Owner.id), func.coalesce(func.sum(Owner.total_amount_wan), 0))
        .where(Owner.is_deleted == 0, Owner.industry.isnot(None)).group_by(Owner.industry).limit(8)
    ).all()

    opp_total = db.execute(select(func.count(Opportunity.id)).where(Opportunity.is_deleted == 0)).scalar() or 0
    amount_total = db.execute(select(func.coalesce(func.sum(Opportunity.amount_wan), 0)).where(Opportunity.is_deleted == 0)).scalar() or 0

    return {
        "success": True,
        "data": {
            "summary": {
                "ownerCount": db.execute(select(func.count(Owner.id)).where(Owner.is_deleted == 0)).scalar() or 0,
                "opportunityCount": opp_total,
                "totalAmountWan": amount_total,
            },
            "byOwnerType": [{"label": t or "未分类", "count": c, "amountWan": a} for t, c, a in by_type_rows],
            "byOwnerScale": [{"label": s or "未分类", "count": c} for s, c in by_scale_rows],
            "topIndustry": [{"label": i or "未分类", "count": c, "amountWan": a} for i, c, a in by_industry_rows],
        },
    }


@router.get("/search")
async def owner_search(keyword: Optional[str] = Query(default=None),
                       page: int = 1, page_size: int = 20,
                       db: Session = Depends(get_db),
                       user: dict = Depends(get_current_user)):
    stmt = select(Owner).where(Owner.is_deleted == 0)
    if keyword:
        kw = keyword.strip()
        stmt = stmt.where(or_(Owner.name.like(f"%{kw}%"), Owner.industry.like(f"%{kw}%")))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    rows = db.execute(
        stmt.order_by(Owner.opportunity_count.desc()).offset(max(0, (page - 1) * page_size)).limit(page_size)
    ).scalars().all()
    return {
        "success": True,
        "data": {
            "total": total,
            "items": [
                {"id": r.id, "name": r.name, "ownerType": r.owner_type, "ownerScale": r.owner_scale,
                 "province": r.province, "city": r.city, "industry": r.industry,
                 "opportunityCount": r.opportunity_count, "totalAmountWan": r.total_amount_wan}
                for r in rows
            ],
        },
    }