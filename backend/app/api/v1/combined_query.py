"""组合查询 API — 对标建设通 adsearch: 多维度「加入筛选」积木式查询(AND 逻辑)。

对应指导文档: docs/gmi-renovation-guide.md A2 / G-阶段二

条件维度(白名单, 防注入):
  company_name  单位名称(模糊)
  province      省份
  city          城市
  company_type  单位类型
  qual_category 资质大类(JOIN qualification)
  qual_level    资质等级
  bid_exists    有中标记录(EXISTS bid_notice)
  credit_exists 有诚信记录(EXISTS credit_record)
  person_name   人员姓名(EXISTS person)

说明: 中标金额区间依赖 bid_notice.meta JSON(供应商明细), 当前阶段以
bid_exists 替代; ES 版本可在索引期抽取金额做区间过滤。
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user

logger = logging.getLogger("combined_query")

router = APIRouter(prefix="/combined-query", tags=["组合查询"])

# 允许的条件键(白名单)
_ALLOWED_CONDITIONS = {
    "company_name", "province", "city", "company_type",
    "qual_category", "qual_level",
    "bid_exists", "credit_exists", "person_name",
}


def _clean_conditions(raw: Optional[str]) -> dict:
    """解析并清洗组合条件: 仅保留白名单键 + 非空标量值。"""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(data, dict):
        return {}
    out = {}
    for k, v in data.items():
        if k not in _ALLOWED_CONDITIONS:
            continue
        if isinstance(v, bool):
            out[k] = v
        elif isinstance(v, (str, int, float)) and v not in (None, ""):
            out[k] = str(v)
    return out


def _build_query(conditions: dict, page: int, page_size: int) -> tuple:
    """根据条件动态拼 SQL(参数化), 返回 (sql, params, count_sql)。

    跨表: qualification / bid_notice / credit_record / person 均用 EXISTS
    相关子查询关联 company, 避免 JOIN 放大行数。
    """
    sql = "SELECT c.id, c.name, c.province, c.city, c.company_type, c.credit_level, c.short_name FROM company c WHERE c.is_deleted=0"
    count_sql = "SELECT COUNT(*) FROM company c WHERE c.is_deleted=0"
    where = []
    params: dict = {}

    if conditions.get("company_name"):
        where.append("c.name LIKE :company_name")
        params["company_name"] = f"%{conditions['company_name']}%"
    if conditions.get("province"):
        where.append("c.province = :province")
        params["province"] = conditions["province"]
    if conditions.get("city"):
        where.append("c.city = :city")
        params["city"] = conditions["city"]
    if conditions.get("company_type"):
        where.append("c.company_type = :company_type")
        params["company_type"] = conditions["company_type"]
    if conditions.get("qual_category"):
        where.append("EXISTS (SELECT 1 FROM qualification q WHERE q.company_id=c.id AND q.is_deleted=0 AND q.category=:qual_category)")
        params["qual_category"] = conditions["qual_category"]
    if conditions.get("qual_level"):
        where.append("EXISTS (SELECT 1 FROM qualification q WHERE q.company_id=c.id AND q.is_deleted=0 AND q.level=:qual_level)")
        params["qual_level"] = conditions["qual_level"]
    if conditions.get("bid_exists") is True:
        where.append("""EXISTS (SELECT 1 FROM bid_notice b WHERE b.is_deleted=0
                        AND (b.purchaser_company_id = c.id OR JSON_SEARCH(b.meta, 'one', c.name) IS NOT NULL))""")
    if conditions.get("credit_exists") is True:
        where.append("EXISTS (SELECT 1 FROM credit_record cr WHERE cr.company_id=c.id AND cr.is_deleted=0)")
    if conditions.get("person_name"):
        where.append("EXISTS (SELECT 1 FROM person p WHERE p.company_id=c.id AND p.is_deleted=0 AND p.name LIKE :person_name)")
        params["person_name"] = f"%{conditions['person_name']}%"

    if where:
        cond = " AND ".join(where)
        sql += " AND " + cond
        count_sql += " AND " + cond
    sql += " ORDER BY c.id DESC LIMIT :limit OFFSET :offset"
    params.update({"limit": page_size, "offset": (page - 1) * page_size})
    return sql, params, count_sql


def _company_stats(db: Session, company_ids: list) -> dict:
    """批量统计: 资质数/中标数/诚信数/人员数(一次查出, 避免 N+1)。"""
    if not company_ids:
        return {}
    stats: dict[int, dict] = {i: {"qual_count": 0, "bid_count": 0, "credit_count": 0, "person_count": 0} for i in company_ids}
    for table, col, key in (
        ("qualification", "company_id", "qual_count"),
        ("credit_record", "company_id", "credit_count"),
        ("person", "company_id", "person_count"),
    ):
        rows = db.execute(text(
            f"SELECT {col}, COUNT(*) FROM {table} WHERE is_deleted=0 AND {col} IN :ids GROUP BY {col}"
        ), {"ids": tuple(company_ids)}).all()
        for cid, cnt in rows:
            if int(cid) in stats:
                stats[int(cid)][key] = int(cnt)
    # bid 数: purchaser_company_id + meta 内 company_id(简化按名称)
    rows = db.execute(text(
        "SELECT purchaser_company_id, COUNT(*) FROM bid_notice WHERE is_deleted=0 AND purchaser_company_id IN :ids GROUP BY purchaser_company_id"
    ), {"ids": tuple(company_ids)}).all()
    for cid, cnt in rows:
        if cid and int(cid) in stats:
            stats[int(cid)]["bid_count"] += int(cnt)
    return stats


@router.get("/options")
async def combined_query_options(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """返回组合查询各条件的可选值(供前端构建器下拉)。"""
    provinces = [r[0] for r in db.execute(text(
        "SELECT DISTINCT province FROM company WHERE is_deleted=0 AND province IS NOT NULL AND province<>'' ORDER BY province"
    )).all()]
    cities = [r[0] for r in db.execute(text(
        "SELECT DISTINCT city FROM company WHERE is_deleted=0 AND city IS NOT NULL AND city<>'' ORDER BY city"
    )).all()]
    company_types = [r[0] for r in db.execute(text(
        "SELECT DISTINCT company_type FROM company WHERE is_deleted=0 AND company_type IS NOT NULL AND company_type<>'' ORDER BY company_type"
    )).all()]
    qual_categories = [r[0] for r in db.execute(text(
        "SELECT DISTINCT category FROM qualification WHERE is_deleted=0 AND category IS NOT NULL AND category<>'' ORDER BY category"
    )).all()]
    qual_levels = [r[0] for r in db.execute(text(
        "SELECT DISTINCT level FROM qualification WHERE is_deleted=0 AND level IS NOT NULL AND level<>'' ORDER BY level"
    )).all()]
    return {
        "success": True,
        "data": {
            "provinces": provinces,
            "cities": cities,
            "company_types": company_types,
            "qual_categories": qual_categories,
            "qual_levels": qual_levels,
        },
    }


@router.get("/search")
async def combined_query_search(
    conditions: str = Query("{}", description="组合条件 JSON, 见 README"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """组合查询检索: 多条件 AND 过滤单位列表, 返回各条件命中摘要与统计。"""
    conds = _clean_conditions(conditions)
    sql, params, count_sql = _build_query(conds, page, page_size)
    total = db.execute(text(count_sql), {k: v for k, v in params.items() if k not in ("limit", "offset")}).scalar() or 0
    rows = db.execute(text(sql), params).all()
    companies = [{"id": r[0], "name": r[1], "province": r[2], "city": r[3],
                  "company_type": r[4], "credit_level": r[5], "short_name": r[6]} for r in rows]
    stats = _company_stats(db, [c["id"] for c in companies])
    for c in companies:
        c.update(stats.get(c["id"], {}))
    summary = {k: v for k, v in conds.items()}
    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": companies,
            "conditions": summary,
            "matched_conditions": [k for k in conds if k in ("company_name", "province", "city", "company_type")],
        },
    }
