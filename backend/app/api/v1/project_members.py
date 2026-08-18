"""项目成员管理 API — 弱关联,保留时间轨迹"""
from typing import Optional
import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, aliased
from sqlalchemy import select, func, and_

from app.database import get_db
from app.models.project_member import ProjectMember
from app.models.project import Project
from app.models.person import Person
from app.models.company import Company, ProjectCompany
from app.middleware.auth import get_current_user, require_permission
from app.schemas.project_member import (
    ProjectMemberCreate, ProjectMemberUpdate,
    ProjectMemberResponse, MemberTimelineResponse,
)
from app.schemas.common import PaginatedResponse
from app.services.neo4j_sync import sync_project_members, sync_project, _run as _neo_run, RELATION_NAMES_ZH

router = APIRouter(prefix="/project-members", tags=["项目成员"])


def _raise_if_manager(db: Session, project_id: int, person_id: int) -> None:
    """项目负责人不允许退出/删除: 抛 400, 需先改派负责人。"""
    proj = db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    ).scalar_one_or_none()
    if proj and proj.manager_id == person_id:
        raise HTTPException(
            status_code=400,
            detail="该成员是项目负责人, 不能退出/删除, 请先在项目编辑中改派负责人后再操作。",
        )


def _sync_project_members_to_neo4j(db: Session, project_id: int) -> None:
    """项目成员变化后, 重建该项目 Neo4j 参与/合作关系(降级)。"""
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
            select(ProjectMember, Person.name, Person.company_id)
            .join(Person, ProjectMember.person_id == Person.id)
            .where(
                ProjectMember.project_id == project_id,
                ProjectMember.is_active == True,
                ProjectMember.is_deleted == False,
                Person.is_deleted == False,
            )
        ).all()
        members = [
            {
                "person_id": pm.person_id,
                "name": pname or "",
                "role": pm.role or "member",
                "company_id": pcompany_id,
            }
            for pm, pname, pcompany_id in rows
        ]
        sync_project_members(project_id, members)

        # ★ 建立公司级参与关系: 成员添加/变更后, 其任职公司也应关联到项目,
        #   与「成员退出→公司解除关联」形成闭环(公司级图谱参与跟随活跃成员任职公司)。
        if members:
            _neo_run(
                """
                MATCH (proj:Project {project_id: $pid})<-[:PARTICIPATES_IN]-(p:Person)-[:WORKS_AT]->(c:Company)
                MERGE (c)-[:PARTICIPATES_IN {name_zh: $rel}]->(proj)
                """,
                pid=project_id,
                rel=RELATION_NAMES_ZH.get("PARTICIPATES_IN", "参与"),
            )

        # ★ 清理失效的公司级参与关系: 当某公司在项目中已无任何活跃成员任职时,
        #   取消其与该项目的 PARTICIPATES_IN 关联, 保持图谱与人员参与一致。
        keep_ids = sorted({m.get("company_id") for m in members if m.get("company_id")})
        _neo_run(
            """
            MATCH (proj:Project {project_id: $pid})<-[r:PARTICIPATES_IN]-(c:Company)
            WHERE NOT c.company_id IN $keep
            DELETE r
            """,
            pid=project_id,
            keep=[int(k) for k in keep_ids] if keep_ids else [0],
        )
    except Exception:  # noqa: BLE001
        pass


@router.get("/timeline/{project_id}", response_model=PaginatedResponse)
async def get_project_members(
    project_id: int,
    include_inactive: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    项目成员时间线 — 支持查询某时间点项目成员构成

    请求示例:
      GET /api/v1/project-members/timeline/1?include_inactive=true

    响应示例:
      ```json
      {
        "total": 5, "page": 1, "page_size": 50,
        "items": [
          {
            "id": 10, "project_id": 1, "person_id": 3,
            "person_name": "张三", "person_code": "EMP-001",
            "role": "manager", "responsibility": "项目统筹",
            "joined_at": "2025-03-01T09:00:00",
            "left_at": null, "is_active": true,
            "person_department": "地质勘探部"
          }
        ]
      }
      ```
    """
    stmt = (
        select(
            ProjectMember,
            Person.name.label("person_name"),
            Person.code.label("person_code"),
            func.ifnull(Person.position, "").label("person_department"),
            func.ifnull(Person.position, "").label("person_position"),
            Person.company_id,
            Company.name.label("company_name"),
        )
        .join(Person, ProjectMember.person_id == Person.id)
        .outerjoin(Company, Person.company_id == Company.id)
        .where(
            ProjectMember.project_id == project_id,
            ProjectMember.is_deleted == False,
        )
    )

    if not include_inactive:
        stmt = stmt.where(ProjectMember.is_active == True)

    # 总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    stmt = stmt.order_by(ProjectMember.joined_at.desc()).offset((page - 1) * page_size).limit(page_size)
    results = db.execute(stmt).all()

    items = []
    for pm, pname, pcode, pdept, ppos, pcompany_id, pcompany_name in results:
        item = MemberTimelineResponse(
            id=pm.id,
            project_id=pm.project_id,
            person_id=pm.person_id,
            role=pm.role,
            responsibility=pm.responsibility,
            stage=pm.stage or "",
            joined_at=pm.joined_at,
            left_at=pm.left_at,
            is_active=pm.is_active,
            ext_attrs=pm.ext_attrs,
            created_at=pm.created_at,
            updated_at=pm.updated_at,
            person_name=pname,
            person_code=pcode,
            person_department=pdept,
            person_position=ppos,
            company_id=pcompany_id,
            company_name=pcompany_name,
        )
        items.append(item)

    return PaginatedResponse(
        total=total, page=page, page_size=page_size, items=items
    )


@router.post("", response_model=ProjectMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_project_member(
    data: ProjectMemberCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_project_crud")),
):
    """
    添加项目成员

    请求示例:
      ```json
      {
        "project_id": 1,
        "person_id": 5,
        "role": "member",
        "responsibility": "野外地质调查",
        "joined_at": "2025-06-01T09:00:00"
      }
      ```
    """
    # 验证项目和人员存在
    project = db.execute(
        select(Project).where(Project.id == data.project_id, Project.is_deleted == False)
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    person = db.execute(
        select(Person).where(Person.id == data.person_id, Person.is_deleted == False)
    ).scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="人员不存在")

    # 检查是否已是活跃成员(同项目同人同阶段才视为重复; 阶段不同可分别参与)
    existing = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == data.project_id,
            ProjectMember.person_id == data.person_id,
            ProjectMember.stage == (data.stage or ""),
            ProjectMember.is_active == True,
            ProjectMember.is_deleted == False,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="该人员在该阶段已是项目活跃成员"
            + (f"（阶段：{data.stage}）" if data.stage else "（全程参与）"),
        )

    joined_at = data.joined_at or datetime.datetime.now()

    member = ProjectMember(
        project_id=data.project_id,
        person_id=data.person_id,
        role=data.role,
        responsibility=data.responsibility,
        stage=data.stage or "",
        joined_at=joined_at,
        is_active=True,
        ext_attrs=data.ext_attrs,
    )
    db.add(member)
    db.commit()
    db.refresh(member)

    # ★ Neo4j 实时同步(成员参与 + 同项目合作关系)
    _sync_project_members_to_neo4j(db, member.project_id)

    return ProjectMemberResponse.model_validate(member)


@router.put("/{member_id}", response_model=ProjectMemberResponse)
async def update_project_member(
    member_id: int,
    data: ProjectMemberUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_project_crud")),
):
    """
    更新项目成员 — 角色变更/退出

    请求示例(退出项目):
      ```json
      {
        "left_at": "2025-07-31T18:00:00",
        "is_active": false
      }
      ```
    """
    member = db.execute(
        select(ProjectMember).where(
            ProjectMember.id == member_id, ProjectMember.is_deleted == False
        )
    ).scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=404, detail="项目成员记录不存在")

    # ★ 负责人保护: 项目负责人不允许退出(设置 left_at 或 is_active=false)
    is_exit = data.left_at is not None or data.is_active is False
    if is_exit and member.person_id:
        _raise_if_manager(db, member.project_id, member.person_id)

    update_data = data.model_dump(exclude_none=True)

    for key, val in update_data.items():
        setattr(member, key, val)

    # 如果退出时间被设置,自动标记为不在职
    if data.left_at and data.is_active is None:
        member.is_active = False

    db.commit()
    db.refresh(member)

    # ★ Neo4j 实时同步(退出/角色变更后重算合作)
    _sync_project_members_to_neo4j(db, member.project_id)

    return ProjectMemberResponse.model_validate(member)


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_project_member(
    member_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_project_crud")),
):
    """物理删除项目成员记录"""
    member = db.execute(
        select(ProjectMember).where(
            ProjectMember.id == member_id, ProjectMember.is_deleted == False
        )
    ).scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=404, detail="项目成员记录不存在")

    # ★ 负责人保护: 项目负责人不允许物理删除
    if member.person_id:
        _raise_if_manager(db, member.project_id, member.person_id)

    db.delete(member)
    db.commit()

    # ★ Neo4j 实时同步(成员移除后重算合作)
    _sync_project_members_to_neo4j(db, member.project_id)
    return None


@router.get("/person-trajectory/{person_id}")
async def get_person_trajectory(
    person_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    人员参与项目轨迹 — 人员主页核心数据

    请求示例:
      GET /api/v1/project-members/person-trajectory/5

    响应示例:
      ```json
      {
        "person_id": 5,
        "person_name": "张三",
        "trajectory": [
          {"project_id": 1, "project_name": "四川探矿", "role": "manager",
           "joined_at": "2024-01-01", "left_at": null, "is_active": true},
          {"project_id": 2, "project_name": "西藏勘查", "role": "member",
           "joined_at": "2023-06-01", "left_at": "2024-12-31", "is_active": false}
        ]
      }
      ```
    """
    person = db.execute(
        select(Person).where(Person.id == person_id, Person.is_deleted == False)
    ).scalar_one_or_none()

    if not person:
        raise HTTPException(status_code=404, detail="人员不存在")

    ManagerPerson = aliased(Person)
    trajectory_rows = db.execute(
        select(
            ProjectMember.id,
            ProjectMember.project_id,
            Project.name,
            ProjectMember.role,
            ProjectMember.stage,
            ProjectMember.joined_at,
            ProjectMember.left_at,
            ProjectMember.is_active,
            Project.status,
            Project.code,
            Project.start_date,
            Project.end_date,
            Project.description,
            Project.ext_attrs,
            ManagerPerson.name,
        )
        .join(Project, ProjectMember.project_id == Project.id)
        .outerjoin(ManagerPerson, ManagerPerson.id == Project.manager_id)
        .where(ProjectMember.person_id == person_id, ProjectMember.is_deleted == False)
        .order_by(ProjectMember.joined_at.desc())
    ).all()

    trajectory = []
    project_ids = set()
    for mid, pid, pname, role, pstage, joined, left, active, pstatus, pcode, \
            pstart, pend, pdesc, pext, pmanager in trajectory_rows:
        ext = pext or {}
        trajectory.append({
            "member_id": mid,
            "project_id": pid,
            "project_name": pname,
            "name": pname,  # ProjectCard 用 project.name
            "role": role,
            "stage": pstage or "",  # 人员参与阶段
            "joined_at": joined.isoformat() if joined else None,
            "left_at": left.isoformat() if left else None,
            "is_active": active,
            # 完整项目字段(供 ProjectCard 渲染; category/amount/stage 为动态字段, 取自 ext_attrs)
            "status": pstatus,
            "code": pcode,
            "category": ext.get("category", "") or "",
            "amount": ext.get("amount", "") or "",
            "start_date": pstart.isoformat() if pstart else None,
            "end_date": pend.isoformat() if pend else None,
            "province": ext.get("province", "") or "",
            "city": ext.get("city", "") or "",
            "stage": ext.get("stage", "") or "",
            "description": pdesc,
            "manager": pmanager,
        })
        project_ids.add(pid)

    # 合作单位: 该人员参与过的项目中, 其他参与人的任职单位(排除本人单位)。
    # 不用 project_company 表——项目单位表常缺数据, 从成员推导更真实(与图谱口径一致)。
    cooperated_map: dict[int, dict] = {}
    if project_ids:
        rows = db.execute(
            select(Company.id, Company.name, Project.id, Project.name,
                   Person.id, Person.name, Person.position)
            .select_from(ProjectMember)
            .join(Person, Person.id == ProjectMember.person_id)
            .join(Project, Project.id == ProjectMember.project_id)
            .join(Company, Company.id == Person.company_id)
            .where(
                ProjectMember.project_id.in_(project_ids),
                ProjectMember.is_deleted == False,
                Person.is_deleted == False,
                Person.company_id.is_not(None),
                Person.company_id != person.company_id,
            )
            .order_by(Project.id, Person.id)
        ).all()
        for cid, cname, pid, pname, perid, pername, perpos in rows:
            entry = cooperated_map.setdefault(cid, {
                "company_id": cid, "name": cname, "projects": [], "persons": [],
            })
            if pid not in {p["id"] for p in entry["projects"]}:
                entry["projects"].append({"id": pid, "name": pname})
            if perid not in {pp["id"] for pp in entry["persons"]}:
                entry["persons"].append({"id": perid, "name": pername, "position": perpos or ""})
    cooperated_companies = sorted(cooperated_map.values(), key=lambda c: c["name"] or "")

    return {
        "person_id": person_id,
        "person_name": person.name,
        "trajectory": trajectory,
        "company_count": len(cooperated_companies),
        "cooperated_companies": cooperated_companies,
    }
