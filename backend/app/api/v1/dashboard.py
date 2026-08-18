"""数据看板 API — HANDOFF §6.2.1"""
from typing import Optional
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, text, case
from pydantic import BaseModel

from app.database import get_db
from app.models.project import Project
from app.models.person import Person
from app.models.project_member import ProjectMember
from app.models.field_meta import FieldMetadata
from app.middleware.auth import get_current_user
from app.services.cache_service import cache_service

router = APIRouter(prefix="/dashboard", tags=["数据看板"])


def _default_date_range():
    today = date.today()
    return today.replace(year=today.year - 1).isoformat(), today.isoformat()

# ── 项目经营汇总 ──
@router.get("/project-summary")
async def project_summary(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """项目经营汇总: 状态分布(label/color 取自 option_set) + 按月趋势"""
    df, dt = _default_date_range()
    date_from = date_from or df
    date_to = date_to or dt

    stmt = select(Project).where(Project.is_deleted == False).where(
        Project.created_at.between(date_from, date_to)
    )
    if department_id:
        stmt = stmt.where(Project.department_id == department_id)
    projects = db.execute(stmt).scalars().all()

    # 状态分布（label/color 来自 option_set）
    status_opts = await cache_service.get_option_set("project_status")
    label_map = {}
    color_map = {}
    if status_opts:
        for item in status_opts.get("items", []):
            label_map[item["value"]] = item["label"]
            color_map[item["value"]] = item.get("color", "")

    status_map = {}
    for p in projects:
        s = p.status
        status_map[s] = status_map.get(s, 0) + 1
    by_status = [
        {"status": s, "label": label_map.get(s, s), "count": c, "color": color_map.get(s, "#1890ff")}
        for s, c in status_map.items()
    ]

    # 按月趋势
    rows = db.execute(text("""
        SELECT DATE_FORMAT(created_at, '%Y-%m') as m, COUNT(*) as created_cnt,
               SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed_cnt
        FROM project WHERE is_deleted=0 AND created_at BETWEEN :df AND :dt
        GROUP BY m ORDER BY m
    """), {"df": date_from, "dt": date_to}).all()
    by_month = [{"month": r[0], "created": r[1], "completed": r[2]} for r in rows]

    # 部门分布
    dept_rows = db.execute(text("""
        SELECT COALESCE(department_id,0), COUNT(*) FROM project
        WHERE is_deleted=0 AND created_at BETWEEN :df AND :dt
        GROUP BY department_id ORDER BY COUNT(*) DESC
    """), {"df": date_from, "dt": date_to}).all()
    by_department = [{"department_id": r[0], "department_name": f"Dept-{r[0]}", "count": r[1]} for r in dept_rows]

    res = {"total_projects": len(projects), "by_status": by_status, "by_month": by_month, "by_department": by_department}
    return {"success": True, "message": "ok", "data": res}


# ── 人员投入看板 ──
@router.get("/person-workload")
async def person_workload(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    department_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """人员投入: project_count + active_project_count + total_days + role_distribution"""
    df, dt = _default_date_range()
    date_from = date_from or df
    date_to = date_to or dt

    members = db.execute(
        select(ProjectMember).where(ProjectMember.is_deleted == False)
    ).scalars().all()

    from datetime import datetime as dt_cls
    df_dt = dt_cls.fromisoformat(date_from)
    dt_dt = dt_cls.fromisoformat(date_to)

    person_agg = {}
    for m in members:
        pid = m.person_id
        if pid not in person_agg:
            person_agg[pid] = {"project_count": 0, "active_project_count": 0, "total_days": 0, "roles": {}}
        person_agg[pid]["project_count"] += 1
        if m.is_active:
            person_agg[pid]["active_project_count"] += 1
        # 区间交集天数
        j = max(m.joined_at, df_dt)
        l = min(m.left_at or dt_dt, dt_dt)
        if j <= l:
            person_agg[pid]["total_days"] += (l - j).days
        person_agg[pid]["roles"][m.role] = person_agg[pid]["roles"].get(m.role, 0) + 1

    # 关联人员姓名 + role label
    role_opts = await cache_service.get_option_set("member_role")
    role_label = {}
    if role_opts:
        for item in role_opts.get("items", []):
            role_label[item["value"]] = item["label"]

    person_ids = list(person_agg.keys())
    persons_out = []
    if person_ids:
        person_rows = db.execute(
            select(Person.id, Person.name).where(Person.id.in_(person_ids), Person.is_deleted == False)
        ).all()
        name_map = {p[0]: p[1] for p in person_rows}
        for pid, agg in person_agg.items():
            persons_out.append({
                "person_id": pid,
                "name": name_map.get(pid, f"ID:{pid}"),
                "project_count": agg["project_count"],
                "active_project_count": agg["active_project_count"],
                "total_days": agg["total_days"],
                "role_distribution": [
                    {"role": r, "label": role_label.get(r, r), "count": c}
                    for r, c in agg["roles"].items()
                ],
            })

    persons_out.sort(key=lambda x: x["total_days"], reverse=True)
    summary = {
        "avg_projects_per_person": round(sum(p["project_count"] for p in persons_out) / max(len(persons_out), 1), 1),
        "total_active_members": sum(1 for p in persons_out if p["active_project_count"] > 0),
    }
    return {"success": True, "message": "ok", "data": {"persons": persons_out[:limit], "summary": summary}}


# ── 指标卡片 ──
@router.get("/metrics")
async def dashboard_metrics(
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    active = db.execute(
        select(func.count(Project.id)).where(Project.is_deleted == False, Project.status == "active")
    ).scalar() or 0

    active_m = db.execute(
        select(func.count(ProjectMember.id)).where(ProjectMember.is_deleted == False, ProjectMember.is_active == True)
    ).scalar() or 0

    avg_dur = db.execute(text(
        "SELECT COALESCE(AVG(DATEDIFF(COALESCE(end_date,CURDATE()),start_date)),0) FROM project WHERE is_deleted=0 AND status='completed'"
    )).scalar() or 0

    this_year = date.today().year
    completed_yr = db.execute(text(
        "SELECT COUNT(*) FROM project WHERE is_deleted=0 AND status='completed' AND YEAR(end_date)=:y"
    ), {"y": this_year}).scalar() or 0

    return {"success": True, "message": "ok", "data": {
        "active_projects": active, "active_members": active_m,
        "avg_project_duration_days": round(float(avg_dur), 1),
        "completed_this_year": completed_yr,
    }}


# ── 动态维度分析 ──
@router.get("/dynamic-dimension")
async def dynamic_dimension(
    field_key: str = Query(..., description="is_filterable=true 的动态字段"),
    entity_type: str = Query(default="project"),
    agg: str = Query(default="count"),
    group_by: Optional[str] = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    meta = db.execute(
        select(FieldMetadata).where(
            FieldMetadata.entity_type == entity_type,
            FieldMetadata.field_key == field_key,
            FieldMetadata.is_filterable == True,
            FieldMetadata.is_deleted == False,
        )
    ).scalar_one_or_none()
    if not meta:
        return {"success": False, "message": f"field '{field_key}' not filterable", "data": {"buckets": []}}

    table = entity_type
    json_path = f"$.{field_key}"

    if meta.data_type in ("select", "switch") and agg not in ("count",):
        return {"success": False, "message": f"agg={agg} not supported for {meta.data_type}, use count", "data": {"buckets": []}}

    if meta.data_type in ("number", "money"):
        expr = f"COALESCE(v_ext_{field_key}, CAST(JSON_UNQUOTE(JSON_EXTRACT(ext_attrs,'{json_path}')) AS DECIMAL(18,2)))"
    else:
        expr = f"JSON_UNQUOTE(JSON_EXTRACT(ext_attrs,'{json_path}'))"

    agg_sql = {"count": "COUNT(*)", "sum": f"SUM({expr})", "avg": f"AVG({expr})", "max": f"MAX({expr})", "min": f"MIN({expr})"}.get(agg, "COUNT(*)")

    group_cols = [f"{expr} as dim_value"]
    if group_by:
        group_cols.append(group_by)
        group_clause = f"dim_value, {group_by}"
    else:
        group_clause = "dim_value"

    sql = f"""
        SELECT {', '.join(group_cols)}, {agg_sql} as agg_val
        FROM {table}
        WHERE is_deleted=0 AND JSON_EXTRACT(ext_attrs,'{json_path}') IS NOT NULL
        GROUP BY {group_clause}
        ORDER BY agg_val DESC LIMIT 20
    """
    rows = db.execute(text(sql)).all()
    buckets = []
    for r in rows:
        if group_by:
            buckets.append({"key": f"{r[0]}/{r[1]}", "value": r[2]})
        else:
            buckets.append({"key": str(r[0]), "value": r[1]})

    return {"success": True, "message": "ok", "data": {"field_key": field_key, "agg": agg, "buckets": buckets}}
