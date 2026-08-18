"""项目跟踪器 API — 线索自动归整到项目 + 按阶段监控。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.project import Project
from app.services import project_tracker as tracker

router = APIRouter(prefix="/projects/tracker", tags=["项目跟踪"])


@router.post("/run")
async def tracker_run(
    limit: int = 3000,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_project_crud")),
):
    """全量增量匹配: 把未关联的 意向/招标/中标 线索归整到项目(幂等, 防张冠李戴)。"""
    result = tracker.match_all_clues(db, limit=limit)
    return {"success": True, "message": f"匹配完成: 意向 {result['intent']} / 线索 {result['web_clue']} / 中标 {result['bid']}",
            "data": result}


@router.post("/mark-read/{clue_id}")
async def tracker_mark_read(
    clue_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """标记一条跟踪情报已读。"""
    tracker.mark_read(db, clue_id)
    return {"success": True}


@router.get("/{project_id}")
async def tracker_list(
    project_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """项目已跟踪线索(按阶段分组: 投资意向期/招标期/中标公示期/施工期)。"""
    project = db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    groups = tracker.tracked_clues(db, project_id)
    total = sum(len(g["items"]) for g in groups)
    return {"success": True, "total": total, "groups": groups,
            "project": {"id": project.id, "name": project.name}}
