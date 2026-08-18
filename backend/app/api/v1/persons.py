"""人员管理 API — 独立维度实体"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, cast, Float

from app.database import get_db
from app.models.person import Person
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.field_meta import FieldMetadata
from app.middleware.auth import get_current_user, require_permission
from app.schemas.person import PersonCreate, PersonUpdate, PersonResponse
from app.schemas.common import PaginatedResponse
from app.services.dynamic_field_engine import validate_with_option_sets
from app.services.cache_service import cache_service
from app.services.audit_service import track_field_changes, compute_ext_attr_changes
from app.services.neo4j_sync import sync_person, remove_person, sync_company_colleagues
from app.services.list_filters import parse_filters, apply_filters
from app.models.company import Company

router = APIRouter(prefix="/persons", tags=["人员管理"])

# 内置字段可排序白名单(防止 SQL 注入; 动态字段单独校验)
PERSON_SORTABLE = {
    "code": Person.code,
    "name": Person.name,
    "position": Person.position,
    "email": Person.email,
    "phone": Person.phone,
    "status": Person.status,
    "created_at": Person.created_at,
    "updated_at": Person.updated_at,
    "is_active": Person.is_active,
}

# 内置字段可筛选白名单(仅等值 IN 筛选)
PERSON_FILTERABLE = {
    "code": Person.code,
    "name": Person.name,
    "position": Person.position,
    "email": Person.email,
    "phone": Person.phone,
    "status": Person.status,
    "is_active": Person.is_active,
}


def _load_meta_list(db: Session, entity_type: str) -> list[FieldMetadata]:
    return db.execute(
        select(FieldMetadata).where(
            FieldMetadata.entity_type == entity_type,
            FieldMetadata.status == "enabled",
            FieldMetadata.is_deleted == False,
        )
    ).scalars().all()


def _company_persons(db: Session, company_id: int) -> list[dict]:
    """单位下全部未删除人员(供同事关系重建)。"""
    if not company_id:
        return []
    rows = db.execute(
        select(Person.id, Person.name).where(
            Person.company_id == company_id,
            Person.is_deleted == False,
        )
    ).all()
    return [{"person_id": int(r[0]), "name": r[1] or ""} for r in rows]


def _sync_person_to_neo4j(db: Session, person: Person, old_company_id: Optional[int] = None) -> None:
    """人员变更后同步到 Neo4j(节点 + 所属单位 + 同事关系), 失败静默降级。"""
    company_name = ""
    comp_province, comp_city = "", ""
    if person.company_id:
        row = db.execute(
            select(Company.name, Company.province, Company.city)
            .where(Company.id == person.company_id, Company.is_deleted == False)
        ).first()
        if row:
            company_name, comp_province, comp_city = row[0] or "", row[1] or "", row[2] or ""
    try:
        sync_person(
            person_id=person.id,
            name=person.name or "",
            position=person.position or "",
            status=person.status or "active",
            company_id=person.company_id,
            company_name=company_name,
            email=person.email or "",
            phone=person.phone or "",
            is_active=bool(person.is_active),
            province=comp_province, city=comp_city,
        )
        # 同事关系: 单位变化时同时重建旧单位与新单位
        companies = {person.company_id, old_company_id}
        for cid in companies:
            if cid:
                sync_company_colleagues(cid, _company_persons(db, cid))
    except Exception:  # noqa: BLE001
        pass


@router.get("", response_model=PaginatedResponse)
async def list_persons(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    is_active: Optional[bool] = None,
    filters: Optional[str] = None,
    sort_field: Optional[str] = None,
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    stmt = select(Person).where(Person.is_deleted == False)

    if status:
        stmt = stmt.where(Person.status == status)
    if is_active is not None:
        stmt = stmt.where(Person.is_active == is_active)
    if keyword:
        stmt = stmt.where(Person.name.contains(keyword))

    # 通用多值筛选(filters JSON: {"字段": ["值1","值2"]})
    if filters:
        fdict = parse_filters(filters)
        if fdict:
            meta = _load_meta_list(db, "person")
            stmt, _ = apply_filters(stmt, Person, fdict, meta, PERSON_FILTERABLE)

    # 排序: 内置字段白名单 + 动态 number/money 字段(JSON_EXTRACT)
    order_col = None
    if sort_field in PERSON_SORTABLE:
        order_col = PERSON_SORTABLE[sort_field]
    elif sort_field:
        meta = _load_meta_list(db, "person")
        dm = next((m for m in meta if m.field_key == sort_field), None)
        if dm and dm.data_type in ("number", "money"):
            order_col = cast(
                func.json_unquote(func.json_extract(Person.ext_attrs, f"$.{sort_field}")),
                Float,
            )
    if order_col is None:
        order_col = Person.created_at
    stmt = stmt.order_by(order_col.asc() if sort_order == "asc" else order_col.desc())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    persons = db.execute(stmt).scalars().all()

    # ── 补充列表展示字段: 公司名 / 最新参与项目时间 / 相关项目 ──
    items = []
    if persons:
        person_ids = [p.id for p in persons]
        # 公司名
        company_names: dict = {}
        cids = {p.company_id for p in persons if p.company_id}
        if cids:
            for cid, nm in db.execute(
                select(Company.id, Company.name).where(
                    Company.id.in_(cids), Company.is_deleted == False
                )
            ):
                company_names[cid] = nm
        # 参与项目: 项目名 + 项目创建时间, 按时间倒序取最新
        proj_by_person: dict = {}
        if person_ids:
            rows = db.execute(
                select(
                    ProjectMember.person_id,
                    Project.name,
                    Project.created_at,
                )
                .join(Project, Project.id == ProjectMember.project_id)
                .where(
                    ProjectMember.person_id.in_(person_ids),
                    ProjectMember.is_deleted == False,
                    Project.is_deleted == False,
                )
                .order_by(ProjectMember.person_id, Project.created_at.desc())
            ).all()
            for pid, pname, pcreated in rows:
                proj_by_person.setdefault(pid, []).append((pname, pcreated))
        for p in persons:
            item = PersonResponse.model_validate(p)
            item.company_name = company_names.get(p.company_id) if p.company_id else None
            plist = proj_by_person.get(p.id, [])
            if plist:
                item.latest_project_time = plist[0][1]
                item.related_projects = "、".join(nm for nm, _ in plist)
            items.append(item)
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.post("/import-real")
async def import_real_person_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_person_crud")),
):
    """导入真实人员 Excel(人事花名册): 按姓名复用更新/创建。

    请求: multipart/form-data, file=xxx.xlsx
    只取业务有效字段: 姓名/主岗(职位)/手机号码(电话)/所属单位/所属部门。
    幂等: 同名人员复用更新, 不重复创建, 可重复导入。
    """
    from app.services.real_person_import import import_real_person
    file_bytes = await file.read()
    try:
        result = import_real_person(db, file_bytes)
    except Exception as e:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=400, detail=f"导入失败: {e}") from e
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "导入失败"))
    return result


@router.get("/{person_id}", response_model=PersonResponse)
async def get_person(
    person_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    person = db.execute(
        select(Person).where(Person.id == person_id, Person.is_deleted == False)
    ).scalar_one_or_none()

    if not person:
        raise HTTPException(status_code=404, detail="person not found")

    resp = PersonResponse.model_validate(person)
    # 详情页补充所属单位名(否则前端「所属单位」为空)
    if person.company_id:
        cname = db.execute(
            select(Company.name).where(Company.id == person.company_id, Company.is_deleted == False)
        ).scalar_one_or_none()
        resp.company_name = cname or None
    return resp


@router.get("/{person_id}/projects")
async def person_projects(
    person_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """某人参与的项目列表（标准分页，区别于轨迹接口）"""
    person = db.execute(
        select(Person).where(Person.id == person_id, Person.is_deleted == False)
    ).scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="person not found")

    stmt = (
        select(ProjectMember, Project)
        .join(Project, ProjectMember.project_id == Project.id)
        .where(ProjectMember.person_id == person_id, ProjectMember.is_deleted == False)
    )
    if not include_inactive:
        stmt = stmt.where(ProjectMember.is_active == True)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    rows = db.execute(
        stmt.order_by(ProjectMember.joined_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = []
    for pm, proj in rows:
        items.append({
            "id": proj.id, "code": proj.code, "name": proj.name,
            "status": proj.status, "role": pm.role, "is_active": pm.is_active,
            "joined_at": pm.joined_at, "left_at": pm.left_at,
        })
    return PaginatedResponse(total=total, page=page, page_size=page_size, items=items)


@router.post("", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
async def create_person(
    data: PersonCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_person_crud")),
):
    existing = db.execute(
        select(Person).where(Person.code == data.code, Person.is_deleted == False)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"person code '{data.code}' already exists")

    # ★ P1-1: 动态字段校验
    if data.ext_attrs:
        meta_list = _load_meta_list(db, "person")
        ok, cleaned, err = await validate_with_option_sets(
            "person", data.ext_attrs, meta_list, cache_svc=cache_service, db=db
        )
        if not ok:
            raise HTTPException(status_code=422, detail=err)
        data.ext_attrs = cleaned

    person = Person(**data.model_dump(exclude_none=True))
    db.add(person)
    db.commit()
    db.refresh(person)

    # ★ Neo4j 实时同步(降级: 失败不影响主流程)
    _sync_person_to_neo4j(db, person)

    return PersonResponse.model_validate(person)


@router.put("/{person_id}", response_model=PersonResponse)
async def update_person(
    person_id: int,
    data: PersonUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_person_crud")),
):
    person = db.execute(
        select(Person).where(Person.id == person_id, Person.is_deleted == False)
    ).scalar_one_or_none()

    if not person:
        raise HTTPException(status_code=404, detail="person not found")

    update_data = data.model_dump(exclude_none=True)

    # ★ P1-2: 记录变更前的值
    old_ext_attrs = dict(person.ext_attrs or {})
    old_builtin = {"name": person.name, "position": person.position, "email": person.email}
    old_company_id = person.company_id

    if "ext_attrs" in update_data and update_data["ext_attrs"]:
        old_ext = person.ext_attrs or {}
        merged = {**old_ext, **update_data["ext_attrs"]}
    else:
        merged = person.ext_attrs or {}

    # ★ P1-1: 校验
    if merged:
        meta_list = _load_meta_list(db, "person")
        ok, cleaned, err = await validate_with_option_sets(
            "person", merged, meta_list, cache_svc=cache_service, db=db
        )
        if not ok:
            raise HTTPException(status_code=422, detail=err)
        update_data["ext_attrs"] = cleaned
    elif "ext_attrs" in update_data and not update_data["ext_attrs"]:
        update_data["ext_attrs"] = merged

    for key, val in update_data.items():
        setattr(person, key, val)

    db.commit()
    db.refresh(person)

    # ★ P1-2: 变更历史
    changes = []
    new_builtin = {"name": person.name, "position": person.position, "email": person.email}
    for field in ("name", "position", "email"):
        if str(old_builtin.get(field, "")) != str(new_builtin.get(field, "")):
            changes.append({
                "field_key": field, "field_label": field,
                "old_value": old_builtin.get(field), "new_value": new_builtin.get(field),
            })
    meta_map = {m.field_key: m.display_name for m in _load_meta_list(db, "person")}
    ext_changes = compute_ext_attr_changes(old_ext_attrs, merged, meta_map)
    changes.extend(ext_changes)
    if changes:
        track_field_changes(db, "person", person.id, user.get("user_id"), changes)
        db.commit()

    # ★ Neo4j 实时同步(含同事关系重建: 旧单位+新单位)
    _sync_person_to_neo4j(db, person, old_company_id=old_company_id)

    return PersonResponse.model_validate(person)


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_person(
    person_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_person_crud")),
):
    person = db.execute(
        select(Person).where(Person.id == person_id, Person.is_deleted == False)
    ).scalar_one_or_none()

    if not person:
        raise HTTPException(status_code=404, detail="person not found")

    del_company_id = person.company_id
    person.is_deleted = True
    db.commit()

    # ★ Neo4j 移除节点(软删时同步删除图谱节点)
    try:
        remove_person(person.id)
    except Exception:  # noqa: BLE001
        pass
    # ★ 重建原单位同事关系(该人员已不在同事集合中)
    try:
        sync_company_colleagues(del_company_id, _company_persons(db, del_company_id)) if del_company_id else None
    except Exception:  # noqa: BLE001
        pass
    return None
