"""报表中心 API — 按 实体/时间/区域/状态/部门 维度聚合统计。

设计:
  - 实体/分组/指标全部走白名单映射(防 SQL 注入), 过滤值参数化。
  - 项目/人员接入数据范围过滤(防绕过列表权限)。
  - 指标: count(所有实体) / amount(仅项目, 合同金额 ext_attrs.contract_amount)。
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission

router = APIRouter(
    prefix="/reports",
    tags=["报表中心"],
    dependencies=[Depends(require_permission("menu_dashboard"))],
)

# 实体白名单: entity_type -> (表名, 有status列, 有department_id列)
_ENTITIES: dict[str, tuple[str, bool, bool]] = {
    "project": ("project", True, True),
    "person": ("person", True, True),
    "company": ("company", False, False),
    "bid": ("bid_notice", False, False),
}

# 实体中文名(前端展示)
_ENTITY_LABELS = {"project": "项目", "person": "人员", "company": "单位", "bid": "中标"}
_DIM_LABELS = {"month": "月份", "quarter": "季度", "year": "年份",
               "status": "状态", "department": "部门", "province": "区域"}


def _group_expr(entity_type: str, group_by: str) -> Optional[str]:
    """分组表达式(白名单)。不支持返回 None。"""
    t = _ENTITIES[entity_type][0]
    if group_by == "month":
        return f"DATE_FORMAT({t}.created_at, '%Y-%m')"
    if group_by == "quarter":
        return f"CONCAT(YEAR({t}.created_at), '-Q', QUARTER({t}.created_at))"
    if group_by == "year":
        return f"YEAR({t}.created_at)"
    if group_by == "status":
        return f"{t}.status" if _ENTITIES[entity_type][1] else None
    if group_by == "department":
        return f"{t}.department_id" if _ENTITIES[entity_type][2] else None
    if group_by == "province":
        return "company.province" if entity_type == "company" \
            else f"JSON_UNQUOTE(JSON_EXTRACT({t}.ext_attrs, '$.province'))"
    return None


def _amount_expr(entity_type: str) -> Optional[str]:
    """金额指标表达式(仅项目合同金额 ext_attrs.amount)。"""
    if entity_type == "project":
        return ("COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(project.ext_attrs, '$.amount')) "
                "AS DECIMAL(18,2)), 0)")
    return None


@router.get("/aggregate")
async def report_aggregate(
    entity_type: str = Query("project"),
    group_by: str = Query("month"),
    metric: str = Query("count"),
    department_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """按维度聚合统计。entity_type∈project/person/company/bid; group_by∈month/quarter/year/status/department/province; metric∈count/amount。"""
    if entity_type not in _ENTITIES:
        raise HTTPException(status_code=400, detail=f"不支持的实体类型: {entity_type}")
    if metric not in ("count", "amount"):
        raise HTTPException(status_code=400, detail="metric 仅支持 count/amount")
    if metric == "amount" and not _amount_expr(entity_type):
        raise HTTPException(status_code=400, detail=f"实体 {entity_type} 不支持金额指标")
    gexpr = _group_expr(entity_type, group_by)
    if not gexpr:
        raise HTTPException(status_code=400, detail=f"实体 {entity_type} 不支持按 {group_by} 分组")

    table = _ENTITIES[entity_type][0]
    conds = [f"{table}.is_deleted = 0"]
    params: dict = {}

    if date_from:
        conds.append(f"{table}.created_at >= :df")
        params["df"] = date_from
    if date_to:
        conds.append(f"{table}.created_at <= :dt")
        params["dt"] = date_to
    if department_id is not None and _ENTITIES[entity_type][2]:
        conds.append(f"{table}.department_id = :dept")
        params["dept"] = department_id

    # 数据范围过滤(项目/人员, 防绕过列表权限)
    if entity_type in ("project", "person"):
        from app.services.data_scope_service import resolve_scope
        scope = resolve_scope(db, user, entity_type)
        if scope.enabled and scope.rule != "ALL":
            scope_conds = []
            if scope.dept_ids:
                scope_conds.append(f"{table}.department_id IN :scope_dept_ids")
                params["scope_dept_ids"] = scope.dept_ids
            obj_ids = scope.grants.get(entity_type) or []
            if obj_ids:
                scope_conds.append(f"{table}.id IN :scope_obj_ids")
                params["scope_obj_ids"] = obj_ids
            if scope_conds:
                conds.append("(" + " OR ".join(scope_conds) + ")")

    select_cols = f"{gexpr} AS grp_key, COUNT(*) AS cnt"
    if metric == "amount":
        select_cols += f", COALESCE(SUM({_amount_expr(entity_type)}), 0) AS amt"

    sql = (f"SELECT {select_cols} FROM {table} WHERE {' AND '.join(conds)} "
           f"GROUP BY grp_key ORDER BY cnt DESC LIMIT :lim")
    params["lim"] = limit
    rows = db.execute(text(sql), params).all()

    data = [{"key": r.grp_key, "count": r.cnt} for r in rows]
    if metric == "amount":
        data = [{**d, "amount": float(r.amt)} for d, r in zip(data, rows)]

    return {
        "success": True,
        "data": data,
        "meta": {
            "entity": entity_type,
            "entity_label": _ENTITY_LABELS.get(entity_type, entity_type),
            "group_by": group_by,
            "group_label": _DIM_LABELS.get(group_by, group_by),
            "metric": metric,
        },
    }
