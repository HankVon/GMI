"""列表通用多值筛选(filters)工具。

前端以 JSON 形式传入: filters={"status": ["active","completed"], "industry": ["矿业"]}
本模块将 filters 转为 SQL WHERE 条件:
  - 内置列: 直接 col.in_(values)
  - 动态字段(ext_attrs): JSON_EXTRACT + IN
  - 白名单校验, 未知字段静默忽略, 防止 SQL 注入
"""
import json
import logging
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def parse_filters(raw: Optional[str]) -> dict:
    """解析 filters 参数, 非法输入返回空 dict。"""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        # 只保留列表类型的值, 元素转 str
        result = {}
        for k, v in data.items():
            if isinstance(v, (list, tuple)):
                vals = [str(x) for x in v if x is not None and str(x) != ""]
                if vals:
                    result[k] = vals
            elif isinstance(v, (str, int, float)) and v not in (None, ""):
                result[k] = [str(v)]
        return result
    except Exception:  # noqa: BLE001
        logger.warning("parse_filters: invalid filters json: %s", raw)
        return {}


def apply_filters(
    stmt,
    model,
    filters: dict,
    meta_list: list,
    builtin: dict,
) -> tuple:
    """把 filters 应用到查询, 返回 (stmt, applied_keys)。

    builtin: 内置列白名单 {field_key: column}
    meta_list: 动态字段元数据列表(含 field_key/data_type/options)
    """
    applied: list[str] = []
    for field, values in filters.items():
        col = builtin.get(field)
        if col is not None:
            stmt = stmt.where(col.in_(values))
            applied.append(field)
            continue
        # 动态字段: 校验元数据存在, 用 JSON_EXTRACT + IN
        dm = next((m for m in meta_list if m.field_key == field), None)
        if dm is not None:
            expr = func.json_unquote(func.json_extract(model.ext_attrs, f"$.{field}"))
            stmt = stmt.where(expr.in_(values))
            applied.append(field)
            continue
        logger.debug("apply_filters: skip unknown field=%s", field)
    return stmt, applied
