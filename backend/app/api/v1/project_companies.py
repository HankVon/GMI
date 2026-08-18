"""项目单位管理 API — 弱关联,保留历史轨迹"""
import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.models.company import ProjectCompany, Company
from app.models.project import Project
from app.middleware.auth import get_current_user, require_permission
from app.schemas.company import ProjectCompanyCreate, ProjectCompanyUpdate, ProjectCompanyResponse, CompanyTimelineResponse
from app.schemas.common import PaginatedResponse
from app.services.neo4j_sync import sync_project, sync_project_companies

router = APIRouter(prefix="/project-companies", tags=["项目单位"])


def _sync_project_companies_to_neo4j(db: Session, project_id: int) -> None:
    """项目单位变化后, 重建该项目 Neo4j 单位参与关系(降级)。"""
    try:
        project = db.execute(
            select(Project).where(Project.id == project_id, Project.is_deleted == False)
        ).scalar_one_or_none()
        if not project:
            return
        _p_ext = project.ext_attrs or {}
        sync_project(project.id, project.name or "", code=project.code or "",
                     status=project.status or "active",
                     category=_p_ext.get("category", "") if isinstance(_p_ext, dict) else "",
                     province=_p_ext.get("province", "") if isinstance(_p_ext, dict) else "",
                     city=_p_ext.get("city", "") if isinstance(_p_ext, dict) else "",
                     county=_p_ext.get("county", "") if isinstance(_p_ext, dict) else "")
        rows = db.execute(
            select(ProjectCompany, Company.name)
            .join(Company, ProjectCompany.company_id == Company.id)
            .where(
                ProjectCompany.project_id == project_id,
                ProjectCompany.is_active == True,
                ProjectCompany.is_deleted == False,
                Company.is_deleted == False,
            )
        ).all()
        companies = [
            {"company_id": pc.company_id, "name": cname or "", "role": pc.role or ""}
            for pc, cname in rows
        ]
        sync_project_companies(project_id, companies)
    except Exception:  # noqa: BLE001
        pass


@router.get("/timeline/{project_id}")
async def get_project_companies(
    project_id: int, include_inactive: bool = False,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db), user: dict = Depends(get_current_user),
):
    stmt = (
        select(ProjectCompany, Company.name.label("company_name"), Company.code.label("company_code"), Company.company_type)
        .join(Company, ProjectCompany.company_id == Company.id)
        .where(ProjectCompany.project_id == project_id, ProjectCompany.is_deleted == False)
    )
    if not include_inactive:
        stmt = stmt.where(ProjectCompany.is_active == True)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    results = db.execute(stmt.order_by(ProjectCompany.joined_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()

    items = []
    for pc, cname, ccode, ctype in results:
        items.append(CompanyTimelineResponse(
            id=pc.id, project_id=pc.project_id, company_id=pc.company_id, role=pc.role,
            joined_at=pc.joined_at, left_at=pc.left_at, is_active=pc.is_active,
            ext_attrs=pc.ext_attrs, created_at=pc.created_at, updated_at=pc.updated_at,
            company_name=cname, company_code=ccode, company_type=ctype,
        ))
    return PaginatedResponse(total=total, page=page, page_size=page_size, items=items)


@router.post("", response_model=ProjectCompanyResponse, status_code=status.HTTP_201_CREATED)
async def add_project_company(data: ProjectCompanyCreate, db: Session = Depends(get_db),
                              user: dict = Depends(require_permission("api_company_crud"))):
    project = db.execute(select(Project).where(Project.id == data.project_id, Project.is_deleted == False)).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    company = db.execute(select(Company).where(Company.id == data.company_id, Company.is_deleted == False)).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="unit not found")
    existing = db.execute(select(ProjectCompany).where(
        ProjectCompany.project_id == data.project_id, ProjectCompany.company_id == data.company_id,
        ProjectCompany.stage == (data.stage or ""),
        ProjectCompany.is_active == True, ProjectCompany.is_deleted == False)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="unit already active on this project for this stage")
    pc = ProjectCompany(project_id=data.project_id, company_id=data.company_id, role=data.role, stage=data.stage or "",
                        joined_at=data.joined_at or datetime.datetime.now(), is_active=True, ext_attrs=data.ext_attrs)
    db.add(pc); db.commit(); db.refresh(pc)

    # ★ Neo4j 实时同步(单位参与项目)
    _sync_project_companies_to_neo4j(db, pc.project_id)
    return ProjectCompanyResponse.model_validate(pc)


@router.put("/{member_id}", response_model=ProjectCompanyResponse)
async def update_project_company(member_id: int, data: ProjectCompanyUpdate,
                                  db: Session = Depends(get_db), user: dict = Depends(require_permission("api_company_crud"))):
    pc = db.execute(select(ProjectCompany).where(ProjectCompany.id == member_id, ProjectCompany.is_deleted == False)).scalar_one_or_none()
    if not pc:
        raise HTTPException(status_code=404, detail="record not found")
    update_data = data.model_dump(exclude_none=True)
    for key, val in update_data.items():
        setattr(pc, key, val)
    if data.left_at and data.is_active is None:
        pc.is_active = False
    db.commit(); db.refresh(pc)

    # ★ Neo4j 实时同步
    _sync_project_companies_to_neo4j(db, pc.project_id)
    return ProjectCompanyResponse.model_validate(pc)


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_project_company(member_id: int, db: Session = Depends(get_db),
                                  user: dict = Depends(require_permission("api_company_crud"))):
    pc = db.execute(select(ProjectCompany).where(ProjectCompany.id == member_id, ProjectCompany.is_deleted == False)).scalar_one_or_none()
    if not pc:
        raise HTTPException(status_code=404, detail="record not found")
    pc.is_deleted = True; pc.is_active = False
    if not pc.left_at:
        pc.left_at = datetime.datetime.now()
    db.commit()

    # ★ Neo4j 实时同步
    _sync_project_companies_to_neo4j(db, pc.project_id)
    return None


@router.get("/company-trajectory/{company_id}")
async def get_company_trajectory(company_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """单位参与项目轨迹"""
    company = db.execute(select(Company).where(Company.id == company_id, Company.is_deleted == False)).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="unit not found")
    rows = db.execute(
        select(ProjectCompany.project_id, Project.name, ProjectCompany.role, ProjectCompany.stage,
               ProjectCompany.joined_at, ProjectCompany.left_at, ProjectCompany.is_active)
        .join(Project, ProjectCompany.project_id == Project.id)
        .where(ProjectCompany.company_id == company_id, ProjectCompany.is_deleted == False)
        .order_by(ProjectCompany.joined_at.desc())
    ).all()
    trajectory = [{"project_id": r[0], "project_name": r[1], "role": r[2], "stage": r[3] or "",
                   "joined_at": r[4].isoformat() if r[4] else None,
                   "left_at": r[5].isoformat() if r[5] else None, "is_active": r[6]} for r in rows]
    return {"company_id": company_id, "company_name": company.name, "trajectory": trajectory}
