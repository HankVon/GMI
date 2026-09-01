"""项目进展管理 API — 手动维护的进展时间线"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.models.project import Project
from app.models.project_progress import ProjectProgress
from app.models.rbac import SysUser
from app.middleware.auth import require_permission, get_current_user
from app.schemas.project_progress import (
    ProjectProgressCreate, ProjectProgressUpdate, ProjectProgressResponse
)
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/project-progress", tags=["项目进展"])


def _require_project(db: Session, project_id: int) -> Project:
    p = db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    ).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="项目不存在")
    return p


def _to_response(item: ProjectProgress) -> ProjectProgressResponse:
    return ProjectProgressResponse.model_validate(item, from_attributes=True)


@router.get("/{project_id}", response_model=PaginatedResponse)
async def list_progress(
    project_id: int,
    page: int = 1, page_size: int = 100,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_project(db, project_id)
    stmt = select(ProjectProgress).where(
        ProjectProgress.project_id == project_id, ProjectProgress.is_deleted == False
    ).order_by(ProjectProgress.sort_order.asc(), ProjectProgress.progress_date.desc())
    total = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar() or 0
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[_to_response(r) for r in rows],
    )


@router.post("", response_model=ProjectProgressResponse, status_code=201)
async def create_progress(
    data: ProjectProgressCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_project_crud")),
):
    _require_project(db, data.project_id)
    item = ProjectProgress(
        project_id=data.project_id, title=data.title, content=data.content,
        progress_date=data.progress_date, sort_order=data.sort_order,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    # 站内通知: 项目新增进展 → 通知项目负责人(关联账号)
    try:
        from app.services.notification import create_notifications
        proj = _require_project(db, data.project_id)
        if proj.manager_id:
            mgr_uid = db.execute(
                select(SysUser.id).where(
                    SysUser.person_id == proj.manager_id,
                    SysUser.is_deleted == False,  # noqa: E712
                )
            ).scalar_one_or_none()
            if mgr_uid:
                create_notifications(db, [mgr_uid], "progress",
                                     f"项目「{(proj.name or '')[:24]}」新增进展",
                                     data.title or "", related_type="project",
                                     related_id=proj.id)
    except Exception:  # noqa: BLE001 - 通知失败不影响主流程
        pass
    return _to_response(item)


@router.put("/{progress_id}", response_model=ProjectProgressResponse)
async def update_progress(
    progress_id: int, data: ProjectProgressUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_project_crud")),
):
    item = db.execute(
        select(ProjectProgress).where(
            ProjectProgress.id == progress_id, ProjectProgress.is_deleted == False
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="进展记录不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return _to_response(item)


@router.delete("/{progress_id}")
async def delete_progress(
    progress_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_project_crud")),
):
    item = db.execute(
        select(ProjectProgress).where(
            ProjectProgress.id == progress_id, ProjectProgress.is_deleted == False
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="进展记录不存在")
    item.is_deleted = True
    db.commit()
    return {"success": True, "message": "已删除"}
