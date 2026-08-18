"""单位管理 API"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, cast, Float, and_, or_

from app.database import get_db
from app.models.company import Company, ProjectCompany
from app.models.project import Project
from app.models.person import Person
from app.models.project_member import ProjectMember
from app.models.field_meta import FieldMetadata
from app.middleware.auth import get_current_user, require_permission
from app.schemas.company import CompanyCreate, CompanyUpdate, CompanyResponse
from app.schemas.common import PaginatedResponse
from app.services.dynamic_field_engine import validate_with_option_sets
from app.services.cache_service import cache_service
from app.services.company_enrich import enrich_company
from app.services.neo4j_sync import sync_company, remove_company
from app.services.list_filters import parse_filters, apply_filters

# 系统保留扩展键: 不参与动态字段校验, 由业务/LLM 补全直接读写
# (extra_contacts/extra_phones 等由 search_llm 合并写入, field_metadata 未配置,
#  若不抽出, 编辑单位保存时会被动态模型 422「该字段不存在或未启用」)
COMPANY_SYSTEM_EXT_KEYS = {"extra_contacts", "extra_phones", "extra_addresses",
                           "_enrich_tried", "source"}


def _split_company_system_keys(ext: dict):
    sys_vals = {k: ext[k] for k in COMPANY_SYSTEM_EXT_KEYS if k in ext}
    rest = {k: v for k, v in ext.items() if k not in COMPANY_SYSTEM_EXT_KEYS}
    return rest, sys_vals


router = APIRouter(prefix="/companies", tags=["单位管理"])

# 内置字段可排序白名单(防止 SQL 注入; 动态字段单独校验)
COMPANY_SORTABLE = {
    "code": Company.code,
    "name": Company.name,
    "short_name": Company.short_name,
    "credit_code": Company.credit_code,
    "credit_level": Company.credit_level,
    "company_type": Company.company_type,
    "industry": Company.industry,
    "province": Company.province,
    "city": Company.city,
    "created_at": Company.created_at,
    "updated_at": Company.updated_at,
}

# 内置字段可筛选白名单(仅等值 IN 筛选)
COMPANY_FILTERABLE = {
    "code": Company.code,
    "name": Company.name,
    "credit_code": Company.credit_code,
    "credit_level": Company.credit_level,
    "company_type": Company.company_type,
    "industry": Company.industry,
    "province": Company.province,
    "city": Company.city,
}


def _load_meta_list(db: Session, entity_type: str) -> list[FieldMetadata]:
    return db.execute(
        select(FieldMetadata).where(
            FieldMetadata.entity_type == entity_type,
            FieldMetadata.status == "enabled",
            FieldMetadata.is_deleted == False,
        )
    ).scalars().all()


@router.get("", response_model=PaginatedResponse)
async def list_companies(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    company_type: Optional[str] = None, keyword: Optional[str] = None,
    filters: Optional[str] = None,
    sort_field: Optional[str] = None,
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    stmt = select(Company).where(Company.is_deleted == False)
    if company_type:
        stmt = stmt.where(Company.company_type == company_type)
    if keyword:
        stmt = stmt.where(Company.name.contains(keyword))

    # 通用多值筛选(filters JSON: {"字段": ["值1","值2"]})
    if filters:
        fdict = parse_filters(filters)
        if fdict:
            # 所在省市: province/city 核心词模糊匹配
            #   值格式: "省核心"(如 "四川") 或 "省核心|市核心"(如 "四川|成都")
            #   数据省/市名可能带或不带后缀, 故用 LIKE %核心% 兼容
            if "province" in fdict and fdict["province"]:
                or_conds = []
                for pc in fdict["province"]:
                    prov_core, _, city_core = pc.partition("|")
                    conds = [Company.province.like(f"%{prov_core}%")]
                    if city_core:
                        conds.append(Company.city.like(f"%{city_core}%"))
                    or_conds.append(and_(*conds))
                stmt = stmt.where(or_(*or_conds))
                del fdict["province"]
            meta = _load_meta_list(db, "company")
            stmt, _ = apply_filters(stmt, Company, fdict, meta, COMPANY_FILTERABLE)

    # 排序: 内置字段白名单 + 动态 number/money 字段(JSON_EXTRACT)
    order_col = None
    if sort_field in COMPANY_SORTABLE:
        order_col = COMPANY_SORTABLE[sort_field]
    elif sort_field:
        meta = _load_meta_list(db, "company")
        dm = next((m for m in meta if m.field_key == sort_field), None)
        if dm and dm.data_type in ("number", "money"):
            order_col = cast(
                func.json_unquote(func.json_extract(Company.ext_attrs, f"$.{sort_field}")),
                Float,
            )
    if order_col is None:
        order_col = Company.created_at
    stmt = stmt.order_by(order_col.asc() if sort_order == "asc" else order_col.desc())

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    companies = db.execute(stmt).scalars().all()

    return PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[CompanyResponse.model_validate(c) for c in companies],
    )


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    company = db.execute(select(Company).where(Company.id == company_id, Company.is_deleted == False)).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="unit not found")
    resp = CompanyResponse.model_validate(company)
    # 附加字段不可探查说明: 对当前为空的字段给出原因 + 建议获取方式
    try:
        from app.services.company_field_notes import get_field_note, FIELD_NOTES
        ext = company.ext_attrs or {}
        resp_dict = resp.model_dump()
        notes = {}
        # 内置列字段
        col_map = {"province": company.province, "city": company.city,
                   "address": company.address, "credit_code": company.credit_code,
                   "company_type": company.company_type}
        for k, v in col_map.items():
            if not v or str(v).strip().lower() in ("", "/", "-", "无", "null", "none"):
                note = get_field_note(k)
                if note:
                    notes[k] = note
        # 动态 ext 字段
        for k in FIELD_NOTES:
            if k in col_map:
                continue
            v = ext.get(k)
            if not v or str(v).strip().lower() in ("", "/", "-", "无", "null", "none"):
                note = get_field_note(k)
                if note:
                    notes[k] = note
        resp_dict["field_notes"] = notes
        return resp_dict
    except Exception:  # noqa: BLE001
        return resp


@router.post("/{company_id}/enrich")
async def enrich_company_endpoint(
    company_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_company_crud")),
):
    """企查查一键补全单位信息: 按名称查工商信息, 回填空字段"""
    company = db.execute(
        select(Company).where(Company.id == company_id, Company.is_deleted == False)
    ).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="unit not found")
    result = await enrich_company(company)
    if not result.get("ok", True):
        db.rollback()
        return {"success": False, "message": result.get("message", "补全失败"), "data": result}
    db.commit()
    return {"success": True, "message": result.get("message", "ok"), "data": result}


@router.post("/{company_id}/enrich-free")
def enrich_company_free_endpoint(
    company_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_company_crud")),
):
    """免费补全单位信息(不依赖付费 API):
    先匹配公告库(即时), 再主动检索四川政府采购网公告(免费权威),
    提取采购人电话/地址回填空字段。查不到的如实返回, 不编造。
    """
    from app.services.company_free_enrich import enrich_company_free

    company = db.execute(
        select(Company).where(Company.id == company_id, Company.is_deleted == False)
    ).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="unit not found")
    result = enrich_company_free(db, company)
    if not result.get("ok", True):
        db.rollback()
        return {"success": False, "message": result.get("message", "免费补全未命中"), "data": result}
    db.commit()
    return {"success": True, "message": result.get("message", "免费补全完成"), "data": result}


@router.put("/{company_id}/set-primary")
async def set_company_primary(
    company_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_company_crud")),
):
    """把某条联系方式设为主要联系方式(选择主要)。

    payload: {kind: "phone"|"address", value: str}
    phone → 设为 ext.contact_phone(并同步 ext.contact); address → 设为 company.address。
    extra_contacts 中保留该值(标记主要), 不删除。
    """
    from pydantic import BaseModel, Field

    class PrimaryPayload(BaseModel):
        kind: str = Field(..., pattern="^(phone|address)$")
        value: str = Field(..., min_length=1)

    data = PrimaryPayload(**payload)
    company = db.execute(
        select(Company).where(Company.id == company_id, Company.is_deleted == False)
    ).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="unit not found")
    ext = dict(company.ext_attrs or {})
    if data.kind == "phone":
        ext["contact_phone"] = data.value
        ext["contact"] = data.value
    else:
        company.address = data.value
    company.ext_attrs = ext
    db.commit()
    return {"success": True, "message": f"已将「{data.value}」设为主要{'电话' if data.kind == 'phone' else '地址'}"}


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(data: CompanyCreate, db: Session = Depends(get_db),
                         user: dict = Depends(require_permission("api_company_crud"))):
    existing = db.execute(select(Company).where(Company.code == data.code, Company.is_deleted == False)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"unit code '{data.code}' already exists")
    if data.ext_attrs:
        meta_list = _load_meta_list(db, "company")
        ok, cleaned, err = await validate_with_option_sets("company", data.ext_attrs, meta_list, cache_svc=cache_service, db=db)
        if not ok:
            raise HTTPException(status_code=422, detail=err)
        data.ext_attrs = cleaned
    company = Company(**data.model_dump(exclude_none=True))
    db.add(company); db.commit(); db.refresh(company)

    # ★ Neo4j 实时同步
    try:
        sync_company(company.id, company.name or "", code=company.code or "",
                     company_type=company.company_type or "",
                     province=company.province or "", city=company.city or "")
    except Exception:  # noqa: BLE001
        pass
    return CompanyResponse.model_validate(company)


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(company_id: int, data: CompanyUpdate, db: Session = Depends(get_db),
                         user: dict = Depends(require_permission("api_company_crud"))):
    company = db.execute(select(Company).where(Company.id == company_id, Company.is_deleted == False)).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="unit not found")
    update_data = data.model_dump(exclude_none=True)
    if "ext_attrs" in update_data and update_data["ext_attrs"]:
        old = company.ext_attrs or {}
        merged = {**old, **update_data["ext_attrs"]}
        # 抽离系统扩展键(extra_contacts 等), 不参与动态字段校验
        biz_ext, sys_ext = _split_company_system_keys(merged)
        meta_list = _load_meta_list(db, "company")
        ok, cleaned, err = await validate_with_option_sets("company", biz_ext, meta_list, cache_svc=cache_service, db=db)
        if not ok:
            raise HTTPException(status_code=422, detail=err)
        update_data["ext_attrs"] = {**cleaned, **sys_ext}
    for key, val in update_data.items():
        setattr(company, key, val)
    db.commit(); db.refresh(company)

    # ★ Neo4j 实时同步
    try:
        sync_company(company.id, company.name or "", code=company.code or "",
                     company_type=company.company_type or "",
                     province=company.province or "", city=company.city or "")
    except Exception:  # noqa: BLE001
        pass
    return CompanyResponse.model_validate(company)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(company_id: int, db: Session = Depends(get_db),
                         user: dict = Depends(require_permission("api_company_crud"))):
    company = db.execute(select(Company).where(Company.id == company_id, Company.is_deleted == False)).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="unit not found")
    company.is_deleted = True; db.commit()

    # ★ Neo4j 移除节点
    try:
        remove_company(company.id)
    except Exception:  # noqa: BLE001
        pass
    return None


@router.get("/{company_id}/persons")
async def company_persons(company_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """本单位人员列表"""
    persons = db.execute(select(Person.id, Person.name, Person.position)
        .where(Person.company_id == company_id, Person.is_deleted == False)).fetchall()
    return {"success": True, "data": [{"id": p[0], "name": p[1], "position": p[2]} for p in persons]}


@router.get("/{company_id}/projects")
async def company_projects(
    company_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """本公司参与的项目列表（project_company 关联 ∪ 本单位人员参与的 project_member 项目）"""
    company = db.execute(
        select(Company).where(Company.id == company_id, Company.is_deleted == False)
    ).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="unit not found")

    # 来源1: project_company 直接关联
    stmt = (
        select(ProjectCompany, Project, ProjectCompany.role)
        .join(Project, ProjectCompany.project_id == Project.id)
        .where(ProjectCompany.company_id == company_id, ProjectCompany.is_deleted == False)
    )
    if not include_inactive:
        stmt = stmt.where(ProjectCompany.is_active == True)
    pc_rows = db.execute(stmt).all()

    # 来源2: 本单位人员参与的 project_member 项目(取人员最近加入的角色)
    pm_rows = db.execute(
        select(Project, ProjectMember.role, ProjectMember.is_active, ProjectMember.joined_at)
        .join(Person, Person.id == ProjectMember.person_id)
        .join(Project, Project.id == ProjectMember.project_id)
        .where(
            Person.company_id == company_id,
            Person.is_deleted == False,
            ProjectMember.is_deleted == False,
            Project.is_deleted == False,
        )
    ).all()

    # 合并去重: project_company 优先, project_member 补充
    merged: dict[int, dict] = {}
    for pc, proj, role in pc_rows:
        merged[proj.id] = {
            "id": proj.id, "code": proj.code, "name": proj.name,
            "status": proj.status, "role": role, "is_active": pc.is_active,
            "joined_at": pc.joined_at, "left_at": pc.left_at,
        }
    for proj, role, is_active, joined_at in pm_rows:
        if proj.id in merged:
            continue  # project_company 已有
        merged[proj.id] = {
            "id": proj.id, "code": proj.code, "name": proj.name,
            "status": proj.status, "role": role or "成员单位",
            "is_active": is_active, "joined_at": joined_at, "left_at": None,
        }

    items = list(merged.values())
    items.sort(key=lambda x: x.get("joined_at") or 0, reverse=True)
    total = len(items)
    start = (page - 1) * page_size
    return PaginatedResponse(total=total, page=page, page_size=page_size, items=items[start:start + page_size])


def _project_card(proj, role, is_active: bool) -> dict:
    """项目卡片: 基础字段 + ext_attrs 常用信息(投资额/类别/阶段/省份城市等)"""
    ext = proj.ext_attrs or {}
    return {
        "id": proj.id, "code": proj.code, "name": proj.name,
        "status": proj.status, "role": role, "is_active": is_active,
        "start_date": proj.start_date.isoformat() if proj.start_date else None,
        "end_date": proj.end_date.isoformat() if proj.end_date else None,
        "amount": ext.get("amount"),
        "category": ext.get("category"),
        "stage": ext.get("stage") or ext.get("project_stage"),
        "province": ext.get("province") or ext.get("location_province"),
        "city": ext.get("city") or ext.get("location_city"),
        "manager": ext.get("manager") or ext.get("project_manager"),
        "description": proj.description,
    }


@router.get("/{company_id}/stats")
async def company_stats(company_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """商情统计: 未竣工项目 / 关联联系人 / 未竣工项目联系人"""
    company = db.execute(
        select(Company).where(Company.id == company_id, Company.is_deleted == False)
    ).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="unit not found")

    # 1) 参与的项目: project_company 关联 ∪ 本单位人员参与的 project_member 项目
    merged: dict[int, dict] = {}
    pc_rows = db.execute(
        select(ProjectCompany, Project, ProjectCompany.role)
        .join(Project, ProjectCompany.project_id == Project.id)
        .where(ProjectCompany.company_id == company_id, ProjectCompany.is_deleted == False, ProjectCompany.is_active == True)
    ).all()
    for pc, proj, role in pc_rows:
        merged[proj.id] = _project_card(proj, role, pc.is_active)
    pm_rows = db.execute(
        select(Project, ProjectMember.role)
        .join(Person, Person.id == ProjectMember.person_id)
        .join(Project, Project.id == ProjectMember.project_id)
        .where(
            Person.company_id == company_id,
            Person.is_deleted == False,
            ProjectMember.is_deleted == False,
            ProjectMember.is_active == True,
            Project.is_deleted == False,
        )
    ).all()
    for proj, role in pm_rows:
        if proj.id in merged:
            continue
        merged[proj.id] = _project_card(proj, role or "成员单位", True)
    projects = list(merged.values())
    unfinished = [p for p in projects if p["status"] == "active"]
    unfinished_ids = [p["id"] for p in unfinished]

    # 2) 本单位人员(关联联系人) — 含联系方式 + 各自参与的未竣工项目
    company_persons = db.execute(
        select(Person.id, Person.name, Person.position, Person.phone, Person.email, Person.company_id)
        .where(Person.company_id == company_id, Person.is_deleted == False)
        .order_by(Person.id)
    ).fetchall()

    # 本单位人员 -> 参与的未竣工项目(经 project_member)
    person_unfinished: dict[int, list[dict]] = {}
    if unfinished_ids:
        pp_rows = db.execute(
            select(Person.id, Project.id, Project.name, Project.code, ProjectMember.role)
            .join(ProjectMember, ProjectMember.person_id == Person.id)
            .join(Project, Project.id == ProjectMember.project_id)
            .where(
                Person.company_id == company_id,
                Person.is_deleted == False,
                ProjectMember.is_deleted == False,
                ProjectMember.is_active == True,
                Project.is_deleted == False,
                Project.id.in_(unfinished_ids),
            )
        ).fetchall()
        for pid, proj_id, proj_name, proj_code, role in pp_rows:
            person_unfinished.setdefault(pid, []).append({
                "id": proj_id, "name": proj_name, "code": proj_code, "role": role,
            })

    related_persons = []
    for p in company_persons:
        pid = p[0]
        related_persons.append({
            "id": pid, "name": p[1], "position": p[2], "phone": p[3],
            "email": p[4], "company_id": p[5],
            "projects": person_unfinished.get(pid, []),
        })

    # 3) 未竣工项目联系人: 仅限【本单位】人员且关联到未竣工项目(去重, 复用上面聚合)
    unfinished_persons = [rp for rp in related_persons if rp["projects"]]

    return {
        "success": True,
        "data": {
            "projects_total": len(projects),
            "projects_unfinished": len(unfinished),
            "unfinished_projects": unfinished,
            "all_projects": projects,  # 全部参与项目(含富字段, 供"项目商机"抽屉)
            "related_persons_total": len(related_persons),
            "related_persons": related_persons,
            "unfinished_persons_total": len(unfinished_persons),
            "unfinished_persons": unfinished_persons,
        },
    }
