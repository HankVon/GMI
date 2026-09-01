"""营销智能体 API — 闭环看板 / 商机评分 / 内容选题推荐"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.services import marketing

router = APIRouter(prefix="/marketing", tags=["营销智能体"])


@router.get("/dashboard")
async def dashboard(days: int = Query(30, ge=1, le=365), user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """营销智能体总览: 感知→决策→执行→反馈 闭环数据。"""
    return {"success": True, **marketing.marketing_dashboard(db, days=days)}


@router.get("/opportunities")
async def opportunities(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """商机评分列表(意向/招标/中标三源, 关键词+地域+时效评分)。"""
    return {"success": True, **marketing.score_opportunities(db, days=days, limit=limit)}


@router.get("/topics")
async def topics(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """内容选题推荐(数据热点 / GEO可见度缺口 / 引用源缺口)。"""
    return {"success": True, **marketing.suggest_topics(db)}
