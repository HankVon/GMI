"""审计日志查询 API"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_

from app.database import get_db
from app.models.audit import AuditLog, FieldChangeHistory
from app.models.project import Project
from app.models.person import Person
from app.models.company import Company
from app.middleware.auth import get_current_user, require_permission
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/audit", tags=["审计日志"])


def _resolve_entity_name(db: Session, entity_type: str, entity_id: int) -> str:
    """反查实体名称(项目/人员/单位)，供日志按项目区分展示"""
    try:
        if entity_type == "project":
            row = db.execute(
                select(Project.name).where(Project.id == entity_id, Project.is_deleted == False)
            ).scalar_one_or_none()
        elif entity_type in ("person", "persons"):
            row = db.execute(
                select(Person.name).where(Person.id == entity_id, Person.is_deleted == False)
            ).scalar_one_or_none()
        elif entity_type in ("company", "companies"):
            row = db.execute(
                select(Company.name).where(Company.id == entity_id, Company.is_deleted == False)
            ).scalar_one_or_none()
        else:
            row = None
        return row if row else ""
    except Exception:
        return ""


@router.get("/field-changes", response_model=PaginatedResponse)
async def list_field_changes(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    resource_name: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_audit")),
):
    """
    字段变更历史列表(可按项目区分)

    请求示例:
      GET /api/v1/audit/field-changes?resource_name=四川&page=1&page_size=20
      GET /api/v1/audit/field-changes?entity_type=project&entity_id=1

    响应中 entity_name 为反查到的实体名称，便于按项目区分查看。
    """
    stmt = select(FieldChangeHistory)

    if entity_type:
        stmt = stmt.where(FieldChangeHistory.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(FieldChangeHistory.entity_id == entity_id)

    # 按实体名(主要是项目名)筛选: 先反查匹配的 id 集合
    if resource_name:
        keyword = f"%{resource_name}%"
        project_ids = db.execute(
            select(Project.id).where(Project.name.like(keyword), Project.is_deleted == False)
        ).scalars().all()
        person_ids = db.execute(
            select(Person.id).where(Person.name.like(keyword), Person.is_deleted == False)
        ).scalars().all()
        company_ids = db.execute(
            select(Company.id).where(Company.name.like(keyword), Company.is_deleted == False)
        ).scalars().all()
        if not (project_ids or person_ids or company_ids):
            # 没有匹配到任何实体，返回空
            return PaginatedResponse(total=0, page=page, page_size=page_size, items=[])
        conds = []
        if project_ids:
            conds.append((FieldChangeHistory.entity_type == "project") & (FieldChangeHistory.entity_id.in_(project_ids)))
        if person_ids:
            conds.append((FieldChangeHistory.entity_type == "person") & (FieldChangeHistory.entity_id.in_(person_ids)))
        if company_ids:
            conds.append((FieldChangeHistory.entity_type == "company") & (FieldChangeHistory.entity_id.in_(company_ids)))
        stmt = stmt.where(or_(*conds))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    changes = db.execute(
        stmt.order_by(FieldChangeHistory.changed_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    return PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[
            {
                "id": c.id,
                "entity_type": c.entity_type,
                "entity_id": c.entity_id,
                "entity_name": _resolve_entity_name(db, c.entity_type, c.entity_id),
                "field_key": c.field_key,
                "field_label": c.field_label,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "changed_by": c.changed_by,
                "changed_at": c.changed_at.isoformat(),
            }
            for c in changes
        ],
    )


@router.get("/operations", response_model=PaginatedResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: str = None,
    resource_type: str = None,
    user_id: int = None,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_audit")),
):
    """
    操作审计日志列表

    请求示例:
      GET /api/v1/audit/operations?resource_type=project&action=delete&page=1
    """
    stmt = select(AuditLog)

    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0

    stmt = stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    logs = db.execute(stmt).scalars().all()

    return PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[
            {
                "id": l.id, "user_id": l.user_id, "username": l.username,
                "action": l.action, "resource_type": l.resource_type,
                "resource_id": l.resource_id, "resource_name": l.resource_name,
                "detail": l.detail, "ip_address": l.ip_address,
                "created_at": l.created_at.isoformat(),
            }
            for l in logs
        ],
    )


@router.get("/field-changes/{entity_type}/{entity_id}")
async def get_field_changes(
    entity_type: str,
    entity_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    查看某个实体的字段变更历史

    请求示例:
      GET /api/v1/audit/field-changes/project/1

    响应示例:
      ```json
      {
        "items": [
          {"field_key": "contract_amount", "field_label": "合同金额",
           "old_value": "null", "new_value": "5000000",
           "changed_by": 1, "changed_at": "2025-06-15T14:30:00"}
        ]
      }
      ```
    """
    stmt = select(FieldChangeHistory).where(
        FieldChangeHistory.entity_type == entity_type,
        FieldChangeHistory.entity_id == entity_id,
    ).order_by(FieldChangeHistory.changed_at.desc())

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0

    changes = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()

    return PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[
            {
                "id": c.id,
                "entity_type": c.entity_type,
                "entity_id": c.entity_id,
                "field_key": c.field_key,
                "field_label": c.field_label,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "changed_by": c.changed_by,
                "changed_at": c.changed_at.isoformat(),
            }
            for c in changes
        ],
    )
