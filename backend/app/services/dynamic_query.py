"""
★ 动态查询引擎 ★
按元数据驱动的动态字段构建SQL筛选条件，核心用到 MySQL 8.0 的:
  - JSON_EXTRACT / JSON_UNQUOTE: 从 ext_attrs 取值
  - GENERATED ALWAYS AS VIRTUAL COLUMN: 为高频筛选字段建虚拟列 + 索引
"""
import re
from typing import Any, Optional, Dict
from sqlalchemy import text, TextClause
from app.models.field_meta import FieldMetadata

# entity_type → 表名/别名映射
ENTITY_TABLE_MAP: Dict[str, str] = {
    "project": "project",
    "person": "person",
    "project_member": "project_member",
    "company": "company",
    "project_company": "project_company",
}

# field_key 合法字符集: 字母开头, 后随字母/数字/下划线。
# 长度上限 60 保证加 "v_ext_" 前缀后仍不超 MySQL 64 字符标识符限制。
_FIELD_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,59}$")


def _assert_safe_field_key(field_key: str) -> str:
    """校验 field_key 安全性。

    field_key 会被拼入 SQL 的 JSON path / 虚拟列名 / 索引名 / 参数名,
    必须限制为纯标识符字符, 防止注入与 DDL 失败。
    """
    if not isinstance(field_key, str) or not _FIELD_KEY_RE.match(field_key):
        raise ValueError(
            f"非法字段名: {field_key!r} (仅允许字母开头, 后随字母/数字/下划线, 长度≤60)"
        )
    return field_key


def _get_table_name(meta: FieldMetadata) -> str:
    """根据元数据的 entity_type 获取表名(严格白名单, 不在映射中则报错而非回退拼接)"""
    table = ENTITY_TABLE_MAP.get(meta.entity_type)
    if not table:
        raise ValueError(f"非法实体类型: {meta.entity_type!r}, 不在表名白名单中")
    return table


def build_ext_attr_filter(
    meta: FieldMetadata,
    operator: str = "eq",
    value: Any = None,
) -> Optional[TextClause]:
    """
    为单个动态字段构建 SQL WHERE 片段

    支持的运算符:
      - eq/neq: 等于/不等于
      - gt/gte/lt/lte: 数值比较
      - like: 模糊匹配
      - in/nin: 包含/不包含
      - is_null/is_not_null: 空值检查

    返回: sqlalchemy TextClause 或 None

    🗃️ MySQL 8.0 示例：
      JSON_EXTRACT(project.ext_attrs, '$.contract_amount') > 1000000
      优先走虚拟列索引: v_ext_contract_amount > 1000000
    """
    table = _get_table_name(meta)
    _assert_safe_field_key(meta.field_key)
    json_path = f"$.{meta.field_key}"
    json_extract = f"JSON_EXTRACT({table}.ext_attrs, '{json_path}')"

    # 数值类型：优先使用虚拟列
    if meta.data_type in ("number", "money"):
        virtual_col = f"v_ext_{meta.field_key}"
        json_extract = f"COALESCE({table}.{virtual_col}, JSON_EXTRACT({table}.ext_attrs, '{json_path}'))"

    # 字符串类型需要 UNQUOTE
    if meta.data_type in ("text", "textarea", "select", "date"):
        json_extract = f"JSON_UNQUOTE({json_extract})"

    if operator == "eq":
        return text(f"{json_extract} = :val_{meta.field_key}")
    elif operator == "neq":
        return text(f"{json_extract} != :val_{meta.field_key}")
    elif operator == "gt":
        return text(f"{json_extract} > :val_{meta.field_key}")
    elif operator == "gte":
        return text(f"{json_extract} >= :val_{meta.field_key}")
    elif operator == "lt":
        return text(f"{json_extract} < :val_{meta.field_key}")
    elif operator == "lte":
        return text(f"{json_extract} <= :val_{meta.field_key}")
    elif operator == "like":
        return text(f"{json_extract} LIKE :val_{meta.field_key}")
    elif operator == "in":
        return text(f"{json_extract} IN :val_{meta.field_key}")
    elif operator == "is_null":
        return text(f"{json_extract} IS NULL")
    elif operator == "is_not_null":
        return text(f"{json_extract} IS NOT NULL")

    return None


def build_order_clause(
    meta: FieldMetadata,
    direction: str = "asc",
) -> TextClause:
    """为动态字段构建 ORDER BY 片段"""
    table = _get_table_name(meta)
    _assert_safe_field_key(meta.field_key)
    json_path = f"$.{meta.field_key}"

    if meta.data_type in ("number", "money"):
        virtual_col = f"v_ext_{meta.field_key}"
        expr = f"COALESCE({table}.{virtual_col}, JSON_EXTRACT({table}.ext_attrs, '{json_path}'))"
    else:
        expr = f"JSON_UNQUOTE(JSON_EXTRACT({table}.ext_attrs, '{json_path}'))"

    dir_keyword = "DESC" if direction.lower() == "desc" else "ASC"
    return text(f"{expr} {dir_keyword}")


def generate_virtual_column_ddl(meta: FieldMetadata) -> Optional[str]:
    """
    根据字段元数据生成 ALTER TABLE ADD VIRTUAL COLUMN 的DDL

    策略：
      - 仅对 is_searchable 或 is_filterable 的字段建虚拟列
      - number/money → DECIMAL(18,2)
      - text/date → VARCHAR(512)
      - 其他类型暂不建虚拟列

    返回: DDL字符串 或 None(不需要虚拟列)
    """
    if not (meta.is_searchable or meta.is_filterable):
        return None

    table = _get_table_name(meta)
    _assert_safe_field_key(meta.field_key)

    col_name = f"v_ext_{meta.field_key}"
    json_path = f"'$.{meta.field_key}'"

    if meta.data_type in ("number", "money"):
        col_type = "DECIMAL(18,2)"
    elif meta.data_type in ("text", "date", "select"):
        col_type = "VARCHAR(512)"
    else:
        return None

    col_def = (
        f"`{col_name}` {col_type} GENERATED ALWAYS AS "
        f"(JSON_UNQUOTE(JSON_EXTRACT(`ext_attrs`, {json_path}))) VIRTUAL"
    )

    ddl = [
        f"ALTER TABLE `{table}` ADD COLUMN {col_def};",
        f"ALTER TABLE `{table}` ADD INDEX `idx_{col_name}` (`{col_name}`);",
    ]

    return "\n".join(ddl)
