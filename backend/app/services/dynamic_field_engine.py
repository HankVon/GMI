"""
★ 动态字段引擎 ★
核心职责：
  1. 按字段元数据在运行时动态生成 Pydantic v2 校验模型
  2. 校验 ext_attrs JSON 数据（服务端唯一权威校验）
  3. ext_attrs 结构约定
  4. 字段权限过滤

ext_attrs 结构约定：
  {
    "field_key_1": value,       // 文本/数字/日期/开关
    "field_key_2": [v1, v2],    // 多选(值数组)
    "field_key_3": {"id": 123, "name": "关联实体名"}  // entity_ref
  }
"""
import decimal
import json
import threading
from typing import Any, Optional
from pydantic import BaseModel, Field, create_model, ValidationError, ConfigDict


class ForbidExtraBase(BaseModel):
    """带 extra=forbid 的基类, 避免 create_model 中 __config__ 与 __base__ 冲突"""
    model_config = ConfigDict(extra="forbid")
import datetime

from app.models.field_meta import FieldMetadata

# ── 数据类型 → Python 类型映射 ──
TYPE_MAP = {
    "text": str,
    "textarea": str,
    "number": float,
    "money": decimal.Decimal,
    "date": str,           # 前端传 "2025-01-01" 字符串
    "select": str,         # 单选=字符串值
    "multi_select": list,  # 多选=值数组
    "switch": bool,
    "entity_ref": dict,    # {"id":..., "name":...}
}


def _build_field_for_meta(meta: FieldMetadata) -> tuple:
    """根据元数据构建 Pydantic Field"""
    py_type = TYPE_MAP.get(meta.data_type, str)
    rules = meta.validation_rules or {}

    kwargs: dict[str, Any] = {}

    # 必填 → None 默认值表示缺少则报错
    if meta.is_required:
        kwargs["default"] = ...
    else:
        kwargs["default"] = None

    # 数值范围
    if meta.data_type in ("number", "money"):
        if "min" in rules:
            kwargs["ge"] = rules["min"]
        if "max" in rules:
            kwargs["le"] = rules["max"]

    # 字符串长度
    if meta.data_type in ("text", "textarea"):
        if "min_length" in rules:
            kwargs["min_length"] = rules["min_length"]
        if "max_length" in rules:
            kwargs["max_length"] = rules["max_length"]

    # 描述
    kwargs["description"] = meta.display_name

    # 封装成 Optional（Pydantic v2 用 union）
    field = Field(**kwargs)

    # 如果是 Optional 的，用 typing.Optional
    if not meta.is_required:
        from typing import Optional as Opt
        return (Opt[py_type], field)

    return (py_type, field)


# ── 动态模型指纹缓存 ──
# 高频校验(批量导入/列表过滤)下每次 create_model 都会新建类定义并占用内存,
# 故以 (entity_type, 字段结构指纹) 为 key 缓存生成的模型类。
# 字段元数据变更(增删/改类型/改校验规则)会改变指纹 → 自动重建, 无过期风险。
_model_cache: dict[tuple[str, str], type[BaseModel]] = {}
_model_cache_lock = threading.Lock()
_MODEL_CACHE_MAX = 128


def _meta_fingerprint(entity_type: str, meta_list: list[FieldMetadata]) -> str:
    """计算决定模型结构的关键属性指纹(只读属性, 不触碰 ORM 脏状态)。"""
    parts = []
    for meta in meta_list:
        if meta.status != "enabled":
            continue
        rules = meta.validation_rules or {}
        parts.append((
            meta.field_key,
            meta.data_type,
            meta.is_required,
            json.dumps(rules, ensure_ascii=False, sort_keys=True, default=str),
        ))
    return json.dumps(parts, ensure_ascii=False, sort_keys=True)


def build_dynamic_model(entity_type: str, meta_list: list[FieldMetadata]) -> type[BaseModel]:
    """
    运行时动态创建 Pydantic 校验模型(带指纹缓存, 字段结构不变时复用类)

    入参:
      entity_type: 实体类型字符串(project/person/...)
      meta_list:   该实体的字段元数据列表

    返回:
      动态生成的 Pydantic v2 BaseModel 子类

    用法:
      model = build_dynamic_model("project", meta_list)
      validated_data = model(**{"contract_amount": 5000000, ...})
    """
    fingerprint = _meta_fingerprint(entity_type, meta_list)
    cache_key = (entity_type, fingerprint)
    cached = _model_cache.get(cache_key)
    if cached is not None:
        return cached

    field_defs: dict[str, tuple] = {}
    for meta in meta_list:
        if meta.status != "enabled":
            continue
        field_type, field = _build_field_for_meta(meta)
        field_defs[meta.field_key] = (field_type, field)

    if not field_defs:
        DynamicModel = create_model(f"Dynamic_{entity_type}_ext", __base__=ForbidExtraBase)
    else:
        DynamicModel = create_model(
            f"Dynamic_{entity_type}_ext",
            **{k: v for k, v in field_defs.items()},
            __base__=ForbidExtraBase,
        )

    with _model_cache_lock:
        # 简单淘汰: 超上限时整体清空(字段元数据极少变动, 重建成本可忽略)
        if len(_model_cache) >= _MODEL_CACHE_MAX:
            _model_cache.clear()
        _model_cache[cache_key] = DynamicModel

    return DynamicModel


def validate_ext_attrs(
    entity_type: str,
    ext_attrs: dict,
    meta_list: list[FieldMetadata],
    option_set_values: Optional[dict[str, set]] = None,
    db = None,
) -> tuple[bool, dict, Optional[str]]:
    """
    校验 ext_attrs 数据

    参数:
      entity_type: 实体类型
      ext_attrs:   待校验的 ext_attrs
      meta_list:   字段元数据列表
      option_set_values: 选项集值映射 {option_set_code: {value1, value2, ...}},
                        用于select/multi_select校验。None时跳过选项集校验。
      db:           SQLAlchemy Session,用于 entity_ref 校验

    返回:
      (成功?, 清洗后的数据, 错误消息)
    """
    if not ext_attrs or not meta_list:
        return True, ext_attrs or {}, None

    # 构建 field_key → display_name 映射
    meta_map = {m.field_key: m.display_name for m in meta_list}
    meta_by_key = {m.field_key: m for m in meta_list}

    try:
        DynamicModel = build_dynamic_model(entity_type, meta_list)
        validated = DynamicModel(**ext_attrs)
        cleaned = validated.model_dump(exclude_none=True)
    except ValidationError as e:
        error_details = []
        for err in e.errors():
            loc_parts = [str(l) for l in err["loc"]]
            # 将 field_key 替换为 display_name
            display_parts = [meta_map.get(p, p) for p in loc_parts]
            loc_display = " → ".join(display_parts)
            msg = err["msg"]
            if "Extra inputs are not permitted" in msg:
                msg = "该字段不存在或未启用"
            error_details.append(f"{loc_display}: {msg}")
        return False, ext_attrs, "; ".join(error_details)

    # ── 必填非空校验 (已提供但为空值视为未填) ──
    for meta in meta_list:
        if meta.status != "enabled" or not meta.is_required:
            continue
        val = cleaned.get(meta.field_key)
        if val is None or val == "" or (isinstance(val, list) and len(val) == 0):
            return False, cleaned, f"{meta.display_name}: 为必填项，不能为空"

    # ── 选项集值校验 (select/multi_select) ──
    if option_set_values is not None:
        for key, val in cleaned.items():
            meta = meta_by_key.get(key)
            if not meta or meta.data_type not in ("select", "multi_select"):
                continue
            if not meta.option_set_code:
                continue
            allowed = option_set_values.get(meta.option_set_code)
            if allowed is None:
                continue
            if meta.data_type == "select":
                if val not in allowed:
                    return False, cleaned, f"{meta.display_name}: 值 '{val}' 不在选项集 '{meta.option_set_code}' 范围内"
            elif meta.data_type == "multi_select":
                if not isinstance(val, list):
                    return False, cleaned, f"{meta.display_name}: 应为多选值数组"
                for item in val:
                    if item not in allowed:
                        return False, cleaned, f"{meta.display_name}: 值 '{item}' 不在选项集 '{meta.option_set_code}' 范围内"

    # ── entity_ref 存在性校验 ──
    if db is not None:
        # 表名严格取自白名单映射(不允许把 option_set_code 直接拼入 SQL)
        REF_TABLE_MAP = {"project": "project", "person": "person", "project_member": "project_member"}
        for key, val in cleaned.items():
            meta = meta_by_key.get(key)
            if not meta or meta.data_type != "entity_ref":
                continue
            if not isinstance(val, dict) or "id" not in val:
                continue
            ref_entity = REF_TABLE_MAP.get(meta.option_set_code or "")
            if not ref_entity:
                continue
            from sqlalchemy import text as sa_text
            check_sql = sa_text(f"SELECT 1 FROM {ref_entity} WHERE id = :rid AND is_deleted = 0")
            exists = db.execute(check_sql, {"rid": val["id"]}).scalar()
            if not exists:
                return False, cleaned, f"{meta.display_name}: 关联实体 id={val['id']} 不存在或已删除"

    return True, cleaned, None


async def validate_with_option_sets(
    entity_type: str,
    ext_attrs: dict,
    meta_list: list[FieldMetadata],
    cache_svc = None,
    db = None,
) -> tuple[bool, dict, Optional[str]]:
    """
    完整校验：Pydantic 类型校验 + 选项集值校验 + entity_ref 校验

    自动从缓存/DB加载需要的选项集值，然后调用 validate_ext_attrs。
    CRUD 路由统一调用此函数。

    内置选项集值局部缓存：同一 validate 调用内同一 option_set_code 只查一次。
    """
    # 收集本实体 select/multi_select 字段的 option_set_code（局部去重）
    opt_codes = set()
    for m in meta_list:
        if m.data_type in ("select", "multi_select") and m.option_set_code:
            opt_codes.add(m.option_set_code)

    # 加载选项集值（缓存优先，局部内存缓存避免重复查询）
    option_set_values: dict[str, set] = {}
    for code in opt_codes:
        items = None
        if cache_svc:
            try:
                opts = await cache_svc.get_option_set(code)
                if opts:
                    items = opts.get("items", [])
            except Exception:
                pass
        if items is None and db is not None:
            from sqlalchemy import select as sa_select
            from app.models.option_set import OptionSet, OptionItem
            os = db.execute(
                sa_select(OptionSet).where(OptionSet.code == code, OptionSet.is_deleted == False)
            ).scalar_one_or_none()
            if os:
                oi_list = db.execute(
                    sa_select(OptionItem).where(OptionItem.option_set_id == os.id, OptionItem.is_deleted == False)
                ).scalars().all()
                items = [{"value": o.value, "label": o.label} for o in oi_list]
        if items:
            option_set_values[code] = {item["value"] for item in items}

    return validate_ext_attrs(entity_type, ext_attrs, meta_list, option_set_values, db=db)


def filter_fields_by_permission(
    meta_list: list[FieldMetadata],
    user_roles: list[str],
    mode: str = "view",
) -> list[FieldMetadata]:
    """
    按用户角色过滤可见字段

    参数:
      meta_list:   完整字段元数据列表
      user_roles:  用户角色列表(如 ["admin","pm"])
      mode:        "view" 或 "edit"

    返回:
      过滤后的字段元数据列表
    """
    perm_key = mode  # "view" 或 "edit"

    filtered = []
    for meta in meta_list:
        perms = meta.field_permissions or {}
        allowed_roles = perms.get(perm_key)

        # 未配置权限 → 所有人可见/可编辑
        if not allowed_roles:
            filtered.append(meta)
            continue

        # 用户任一角色在允许列表中即可
        if any(role in allowed_roles for role in user_roles):
            filtered.append(meta)

    return filtered
