"""项目管理 API"""
import io
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_, cast, Float, exists, update

from app.database import get_db
from app.models.project import Project
from app.models.field_meta import FieldMetadata
from app.middleware.auth import get_current_user, require_permission
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.schemas.common import PaginatedResponse, APIResponse
from app.services.dynamic_field_engine import validate_with_option_sets
from app.services.cache_service import cache_service
from app.services.audit_service import track_field_changes, compute_ext_attr_changes
from app.services.neo4j_sync import remove_project, sync_project_complete
from app.services.list_filters import parse_filters, apply_filters
from app.models.person import Person
from app.models.project_member import ProjectMember
from app.models.project_progress import ProjectProgress
from app.models.company import Company, ProjectCompany

# 系统保留扩展键: 不参与动态字段校验, 由业务直接读写(项目省份/城市/县, 存 ext_attrs.province/city/county)
# 另外豁免 data_pipeline 流水线写入的业务字段(owner/agency/source/owner_addr/agency_addr/agency_phone/
# contact_phone/contact_person/tender_result): 这些字段由公告解析自动写入 ext_attrs,
# 前端编辑保存时原样回传, 若参与动态字段校验会因 field_metadata 未配置报 422「该字段不存在或未启用」。
SYSTEM_EXT_KEYS = {
    "province", "city", "county",
    "owner", "agency", "source",
    "owner_addr", "agency_addr", "agency_phone",
    "contact_phone", "contact_person", "tender_result",
}


def _split_system_keys(ext: dict):
    """把系统保留键从 ext_attrs 中抽出, 返回 (业务字段, 系统键值)。"""
    sys_vals = {k: ext[k] for k in SYSTEM_EXT_KEYS if k in ext}
    rest = {k: v for k, v in ext.items() if k not in SYSTEM_EXT_KEYS}
    return rest, sys_vals

router = APIRouter(prefix="/projects", tags=["项目管理"])

# 内置字段可排序白名单(防止 SQL 注入; 动态字段单独校验)
PROJECT_SORTABLE = {
    "code": Project.code,
    "name": Project.name,
    "status": Project.status,
    "start_date": Project.start_date,
    "end_date": Project.end_date,
    "created_at": Project.created_at,
    "updated_at": Project.updated_at,
    "last_progress_date": None,  # 占位, 在 list_projects 中绑定子查询列
    "is_active": Project.is_active,
}

# 内置字段可筛选白名单(仅做等值 IN 筛选; last_progress_title 等关联字段暂不支持)
PROJECT_FILTERABLE = {
    "code": Project.code,
    "name": Project.name,
    "status": Project.status,
    "is_active": Project.is_active,
    "created_at": Project.created_at,
    "updated_at": Project.updated_at,
}


def _load_meta_list(db: Session, entity_type: str) -> list[FieldMetadata]:
    return db.execute(
        select(FieldMetadata).where(
            FieldMetadata.entity_type == entity_type,
            FieldMetadata.status == "enabled",
            FieldMetadata.is_deleted == False,
        )
    ).scalars().all()


def _sync_project_to_neo4j_background(project_id: int) -> None:
    """后台任务: 项目变更后全量同步到 Neo4j(节点+成员参与/合作+单位参与)。

    在独立 DB Session 中执行(请求的 session 已关闭), 失败静默降级, 不阻塞保存接口响应。
    """
    try:
        db: Session = next(get_db())
        try:
            project = db.execute(
                select(Project).where(Project.id == project_id, Project.is_deleted == False)
            ).scalar_one_or_none()
            if project is None:
                return
            # 成员(仅活跃且未删除)
            member_rows = db.execute(
                select(ProjectMember, Person.name, Person.company_id)
                .join(Person, ProjectMember.person_id == Person.id)
                .where(
                    ProjectMember.project_id == project.id,
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
                for pm, pname, pcompany_id in member_rows
            ]
            # 单位(仅活跃且未删除)
            company_rows = db.execute(
                select(ProjectCompany, Company.name)
                .join(Company, ProjectCompany.company_id == Company.id)
                .where(
                    ProjectCompany.project_id == project.id,
                    ProjectCompany.is_active == True,
                    ProjectCompany.is_deleted == False,
                    Company.is_deleted == False,
                )
            ).all()
            companies = [
                {
                    "company_id": pc.company_id,
                    "name": cname or "",
                    "role": pc.role or "",
                }
                for pc, cname in company_rows
            ]
            sync_project_complete(
                project, members=members, companies=companies,
            )
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        pass


def _remove_project_background(project_id: int) -> None:
    """后台任务: 删除项目时异步移除 Neo4j 节点, 失败静默, 不阻塞删除响应。"""
    try:
        remove_project(project_id)
    except Exception:  # noqa: BLE001
        pass


@router.get("", response_model=PaginatedResponse)
async def list_projects(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    is_active: Optional[bool] = None,
    category: Optional[str] = None,
    days: Optional[int] = Query(None, ge=0, description="时间窗(近N天, 按更新时间 last_progress_date 过滤, 0=全部)"),
    filters: Optional[str] = None,
    sort_field: Optional[str] = None,
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    # 每个项目最近一次进展(日期 + 标题): 窗口函数取每个项目最新一条; 无进展则为 NULL
    rn = func.row_number().over(
        partition_by=ProjectProgress.project_id,
        order_by=(ProjectProgress.progress_date.desc(), ProjectProgress.id.desc()),
    ).label("rn")
    progress_subq = (
        select(
            ProjectProgress.project_id,
            ProjectProgress.progress_date.label("last_progress_date"),
            ProjectProgress.title.label("last_progress_title"),
            rn,
        )
        .where(ProjectProgress.is_deleted == False)
        .subquery()
    )
    latest_progress_subq = (
        select(
            progress_subq.c.project_id,
            progress_subq.c.last_progress_date,
            progress_subq.c.last_progress_title,
        )
        .where(progress_subq.c.rn == 1)
        .subquery()
    )
    last_progress_col = latest_progress_subq.c.last_progress_date
    last_title_col = latest_progress_subq.c.last_progress_title
    # 显式同时选中 Project 实体与进展日期/标题列
    stmt = (
        select(Project, last_progress_col, last_title_col)
        .where(Project.is_deleted == False)
        .outerjoin(latest_progress_subq, latest_progress_subq.c.project_id == Project.id)
    )

    if status:
        stmt = stmt.where(Project.status == status)
    if is_active is not None:
        stmt = stmt.where(Project.is_active == is_active)
    if keyword:
        stmt = stmt.where(
            Project.name.contains(keyword) | Project.code.contains(keyword)
        )
    # 按项目类别筛选(ext_attrs.category)
    if category:
        stmt = stmt.where(
            func.json_unquote(func.json_extract(Project.ext_attrs, "$.category")) == category
        )

    # 时间窗: 按最近进展日期(无进展则创建时间)过滤, 支持「近30/90/365天/全部」
    if days:
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=days)
        stmt = stmt.where(
            func.coalesce(last_progress_col, Project.created_at) >= cutoff
        )

    # 通用多值筛选(filters JSON: {"字段": ["值1","值2"]})
    if filters:
        fdict = parse_filters(filters)
        if fdict:
            meta = _load_meta_list(db, "project")
            stmt, _ = apply_filters(stmt, Project, fdict, meta, PROJECT_FILTERABLE)
            # 项目阶段: 最新进展标题 IN
            if "last_progress_title" in fdict and fdict["last_progress_title"]:
                stmt = stmt.where(last_title_col.in_(fdict["last_progress_title"]))
            # 所在省市区县: 优先项目自身 ext_attrs.province/city/county, 兜底关联单位公司 province/city,
            # 按核心词模糊匹配。值格式: "省核心"(如 "四川") / "省核心|市核心"(如 "四川|成都")
            #                              / "省核心|市核心|县核心"(如 "四川|成都|双流")
            # 数据兼容性(历史数据把「市名」塞在 province 字段, 如 province="绵阳市游仙区"):
            #   市级匹配 → 同时查 $.city 与 $.province(公司侧同查 Company.city/Company.province)
            #   县级匹配 → 同时查 $.county/$.city/$.province(公司侧 Company.ext_attrs.county/Company.city/province)
            if "province_city" in fdict and fdict["province_city"]:
                or_conds = []
                own_or_conds = []
                for pc in fdict["province_city"]:
                    parts = pc.split("|")
                    prov_core = parts[0] if len(parts) > 0 else ""
                    city_core = parts[1] if len(parts) > 1 else ""
                    county_core = parts[2] if len(parts) > 2 else ""
                    # 公司侧(关联单位): 省 + 市 + 县 用 AND 分组; 市/县匹配同时查 province/city 字段(兼容旧数据)
                    conds = [
                        or_(
                            Company.province.like(f"%{prov_core}%"),
                            Company.city.like(f"%{prov_core}%"),
                        )
                    ]
                    if city_core:
                        conds.append(
                            or_(
                                Company.city.like(f"%{city_core}%"),
                                Company.province.like(f"%{city_core}%"),
                            )
                        )
                    if county_core:
                        conds.append(
                            or_(
                                func.json_unquote(func.json_extract(Company.ext_attrs, "$.county")).like(f"%{county_core}%"),
                                Company.city.like(f"%{county_core}%"),
                                Company.province.like(f"%{county_core}%"),
                            )
                        )
                    or_conds.append(and_(*conds))
                    # 项目自身 ext_attrs 省市县匹配(JSON_EXTRACT 取值后 LIKE), 同样 AND 分组 + 字段兼容
                    _prov_expr = func.json_unquote(func.json_extract(Project.ext_attrs, "$.province"))
                    _city_expr = func.json_unquote(func.json_extract(Project.ext_attrs, "$.city"))
                    _county_expr = func.json_unquote(func.json_extract(Project.ext_attrs, "$.county"))
                    own = [or_(_prov_expr.like(f"%{prov_core}%"), _city_expr.like(f"%{prov_core}%"))]
                    if city_core:
                        own.append(or_(_city_expr.like(f"%{city_core}%"), _prov_expr.like(f"%{city_core}%")))
                    if county_core:
                        own.append(
                            or_(_county_expr.like(f"%{county_core}%"), _city_expr.like(f"%{county_core}%"),
                                _prov_expr.like(f"%{county_core}%"))
                        )
                    own_or_conds.append(and_(*own))
                stmt = stmt.where(
                    or_(
                        *own_or_conds,
                        exists(
                            select(1)
                            .select_from(ProjectCompany)
                            .join(Company, Company.id == ProjectCompany.company_id)
                            .where(
                                ProjectCompany.project_id == Project.id,
                                ProjectCompany.is_deleted == False,
                                Company.is_deleted == False,
                                or_(*or_conds),
                            )
                        ),
                    )
                )

    # ── 数据范围过滤(分发权限): 启用数据范围的用户按配置过滤;
    #    未启用则保持现有行为(admin 全量, 普通用户只看本部门及未归属部门项目)。
    from app.services.data_scope_service import resolve_scope, scope_filter
    scope = resolve_scope(db, user, "project")
    cond = scope_filter(scope, Project, "project",
                        dept_id_col=Project.department_id,
                        user_id=user.get("user_id"))
    if cond is not None:
        stmt = stmt.where(cond)
    else:
        user_dept = user.get("department_id")
        user_roles = user.get("roles", [])
        if user_dept and "admin" not in user_roles:
            stmt = stmt.where((Project.department_id == user_dept) | (Project.department_id.is_(None)))

    # ── 排序: 内置字段白名单; 动态字段仅允许 number/money 用 JSON_EXTRACT 排序 ──
    order_col = None
    if sort_field in PROJECT_SORTABLE:
        order_col = PROJECT_SORTABLE[sort_field]
        if sort_field == "last_progress_date":
            order_col = last_progress_col
    elif sort_field:
        # 动态字段: 校验在元数据中且为数值类型, 防止任意字段名注入
        meta = _load_meta_list(db, "project")
        dm = next((m for m in meta if m.field_key == sort_field), None)
        if dm and dm.data_type in ("number", "money"):
            order_col = cast(
                func.json_unquote(func.json_extract(Project.ext_attrs, f"$.{sort_field}")),
                Float,
            )
    if order_col is None:
        order_col = Project.created_at
    stmt = stmt.order_by(order_col.asc() if sort_order == "asc" else order_col.desc())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(stmt).all()  # (Project, last_progress_date, last_progress_title)

    # ── 补充省份城市(含区县): 优先取项目自身 ext_attrs.province/city/county(项目内可直接编辑),
    #    没有则回退取项目关联单位(ProjectCompany)中任一单位的 province/city/county ──
    proj_ids = [p.id for p, _, _ in rows]
    loc_map: dict = {}
    own_map: dict = {}
    if proj_ids:
        # 项目自身维护的省份市区县(ext_attrs)
        for p, _, _ in rows:
            ext = p.ext_attrs or {}
            prov = (ext.get("province") or "").strip()
            city = (ext.get("city") or "").strip()
            county = (ext.get("county") or "").strip()
            if prov or city or county:
                own_map[p.id] = "".join(x for x in (prov, city, county) if x)
        # 关联单位兜底(含 ext_attrs.county)
        for pid, prov, city, county in db.execute(
            select(ProjectCompany.project_id, Company.province, Company.city,
                   func.json_unquote(func.json_extract(Company.ext_attrs, "$.county")))
            .join(Company, Company.id == ProjectCompany.company_id)
            .where(
                ProjectCompany.project_id.in_(proj_ids),
                ProjectCompany.is_deleted == False,
                Company.is_deleted == False,
            )
        ):
            if pid not in own_map and (prov or city or county):
                loc_map[pid] = "".join(x for x in (prov or "", city or "", county or "") if x)

    items = []
    for p, lpd, lpt in rows:
        item = ProjectResponse.model_validate(p)
        item.last_progress_date = lpd
        item.last_progress_title = lpt
        item.province_city = own_map.get(p.id) or loc_map.get(p.id) or ""
        items.append(item)

    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    project = db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    ).scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="project not found")

    return ProjectResponse.model_validate(project)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_project_crud")),
):
    existing = db.execute(
        select(Project).where(Project.code == data.code, Project.is_deleted == False)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"project code '{data.code}' already exists")

    # ★ P1-1: 动态字段校验(系统保留键 province/city 抽出, 校验后合并回)
    if data.ext_attrs:
        rest, sys_vals = _split_system_keys(data.ext_attrs)
        if rest:
            meta_list = _load_meta_list(db, "project")
            ok, cleaned, err = await validate_with_option_sets(
                "project", rest, meta_list, cache_svc=cache_service, db=db
            )
            if not ok:
                raise HTTPException(status_code=422, detail=err)
            cleaned.update(sys_vals)
            data.ext_attrs = cleaned
        else:
            data.ext_attrs = dict(sys_vals)

    project = Project(**data.model_dump(exclude_none=True))
    db.add(project)
    db.commit()
    db.refresh(project)

    # ★ Neo4j 异步同步(后台任务, 不阻塞保存响应)
    background_tasks.add_task(_sync_project_to_neo4j_background, project.id)

    return ProjectResponse.model_validate(project)


@router.post("/import-real")
async def import_real_project_endpoint(
    file: UploadFile = File(...),
    deep_enrich: bool = Form(True),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_project_crud")),
):
    """导入真实项目 Excel: 完整导入(公司/人员/项目/关联/Neo4j 图谱)。

    请求: multipart/form-data, file=xxx.xlsx, deep_enrich=true/false
      deep_enrich=false: 快速导入, 跳过 AI 分类与单位信息补全(大文件提速, 只入库源数据+图谱)。
    列要求(首行表头): 项目名称/法人单位/项目负责人/项目负责人联系电话/合同金额/
      项目开工日期/甲方单位名称/甲方纳税人代码/业主联系人/业主联系人电话等。
    幂等: 已存在的公司/人员/项目/关联自动复用, 可重复导入。
    """
    from app.services.import_task import submit_import
    from app.services.real_project_import import import_real_project

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="上传文件为空")
    from app.utils.upload_security import check_upload_file
    _err = check_upload_file(file_bytes, file.filename or "")
    if _err:
        raise HTTPException(status_code=400, detail=_err)

    def _runner(sdb, data, progress):
        return import_real_project(sdb, data, progress=progress,
                                   skip_enrich=not deep_enrich)

    tid = submit_import("projects", file_bytes, user["user_id"], _runner)
    return {
        "success": True,
        "task_id": tid,
        "entity_type": "projects",
        "deep_enrich": deep_enrich,
        "message": ("导入已提交, 快速模式(跳过 AI 补全)" if not deep_enrich
                    else "导入已提交, 正在后台执行(单位信息补全较慢, 请耐心等待)"),
    }


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_project_crud")),
):
    project = db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    ).scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="project not found")

    update_data = data.model_dump(exclude_none=True)

    # ★ manager_id 显式传 None 时清空负责人(exclude_none 会丢弃 None, 需特殊处理)
    raw = data.model_dump()
    if "manager_id" in raw and raw["manager_id"] is None:
        update_data["manager_id"] = None

    # ★ 负责人必须是该项目的参与成员(在途), 与前端「从参与成员中选择」保持一致
    if "manager_id" in update_data and update_data["manager_id"] is not None:
        mid_ok = db.execute(
            select(ProjectMember.id).where(
                ProjectMember.project_id == project.id,
                ProjectMember.person_id == update_data["manager_id"],
                ProjectMember.is_deleted == False,
                ProjectMember.is_active == True,
            )
        ).scalar_one_or_none()
        if not mid_ok:
            raise HTTPException(
                status_code=400,
                detail="项目负责人必须是该项目的参与成员，请先从参与成员中选择。",
            )

    # ★ P1-2: 记录变更前的值(ext_attrs 合并前)
    old_ext_attrs = dict(project.ext_attrs or {})
    old_builtin = {"name": project.name, "status": project.status, "description": project.description}

    # ext_attrs 合并更新
    if "ext_attrs" in update_data and update_data["ext_attrs"]:
        old_ext = project.ext_attrs or {}
        merged = {**old_ext, **update_data["ext_attrs"]}
    else:
        merged = project.ext_attrs or {}

    # ★ P1-1: 对合并后的 ext_attrs 做整体校验(系统保留键 province/city 抽出, 校验后合并回)
    if merged:
        rest, sys_vals = _split_system_keys(merged)
        if rest:
            meta_list = _load_meta_list(db, "project")
            ok, cleaned, err = await validate_with_option_sets(
                "project", rest, meta_list, cache_svc=cache_service, db=db
            )
            if not ok:
                raise HTTPException(status_code=422, detail=err)
            cleaned.update(sys_vals)
            update_data["ext_attrs"] = cleaned
        else:
            update_data["ext_attrs"] = dict(sys_vals)
    elif "ext_attrs" in update_data and not update_data["ext_attrs"]:
        update_data["ext_attrs"] = merged

    # 记录变更前的负责人(供角色联动)
    _prev_manager = project.manager_id

    for key, val in update_data.items():
        setattr(project, key, val)

    # ★ 负责人与成员角色联动: manager_id 变更时, 同步该项目在途成员 role
    #    (人员详情「负责项目」统计基于 project_member.role == "manager")
    if "manager_id" in update_data:
        old_mgr = _prev_manager
        new_mgr = update_data.get("manager_id")
        if old_mgr and old_mgr != new_mgr:
            # 旧负责人 role 降为普通成员(若其仍在项目在途成员中)
            db.execute(
                update(ProjectMember)
                .where(
                    ProjectMember.project_id == project.id,
                    ProjectMember.person_id == old_mgr,
                    ProjectMember.is_active == True,
                    ProjectMember.is_deleted == False,
                )
                .values(role="member")
            )
        if new_mgr:
            # 新负责人 role 设为 manager
            db.execute(
                update(ProjectMember)
                .where(
                    ProjectMember.project_id == project.id,
                    ProjectMember.person_id == new_mgr,
                    ProjectMember.is_active == True,
                    ProjectMember.is_deleted == False,
                )
                .values(role="manager")
            )

    db.commit()
    db.refresh(project)

    # ★ P1-2: 记录字段变更历史
    changes = []
    # 内置字段差异
    new_builtin = {"name": project.name, "status": project.status, "description": project.description}
    for field in ("name", "status", "description"):
        if str(old_builtin.get(field, "")) != str(new_builtin.get(field, "")):
            changes.append({
                "field_key": field,
                "field_label": field,
                "old_value": str(old_builtin.get(field, "")),
                "new_value": str(new_builtin.get(field, "")),
            })
    # ext_attrs 差异
    meta_map = {m.field_key: m.display_name for m in _load_meta_list(db, "project")}
    ext_changes = compute_ext_attr_changes(old_ext_attrs, merged, meta_map)
    changes.extend(ext_changes)
    if changes:
        track_field_changes(db, "project", project.id, user.get("user_id"), changes)
        db.commit()

    # ★ Neo4j 异步同步(后台任务, 不阻塞保存响应)
    background_tasks.add_task(_sync_project_to_neo4j_background, project.id)

    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_project_crud")),
):
    project = db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    ).scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="project not found")

    project.is_deleted = True
    db.commit()

    # ★ Neo4j 异步移除节点(后台任务, 不阻塞删除响应)
    background_tasks.add_task(_remove_project_background, project.id)
    return None
