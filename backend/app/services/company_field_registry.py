"""公司动态字段注册服务 — 免费补全提取到已有字段未覆盖的新信息时, 自动创建字段并保存。

场景: 免费补全从公开渠道提取到「传真/邮编/办公时间」等, field_metadata 中若无对应字段,
     则动态创建(幂等), 使该字段能被动态表单/详情页展示, 并把提取值写入 ext_attrs。
"""
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.field_meta import FieldMetadata

logger = logging.getLogger("company_field_registry")

# 新字段的中文名映射(供自动注册 display_name)
_DYNAMIC_FIELD_LABELS: dict = {
    "fax": "传真",
    "postal_code": "邮政编码",
    "office_hours": "办公时间",
    "contact_phone": "联系电话",
    "contact_person": "联系人",
    "website": "官方网站",
    "contact_email": "电子邮箱",
    "summary": "单位简介",
    "business_scope": "经营范围",
    "belong_org": "登记机关",
    "reg_no": "注册号",
    "establish_date": "成立日期",
    "oper_status": "经营状态",
    "registered_capital": "注册资本",
    "econ_kind": "企业类型",
}

# 新字段的数据类型映射
_DYNAMIC_FIELD_TYPES: dict = {
    "fax": "text",
    "postal_code": "text",
    "office_hours": "text",
    "postal": "text",
}


def ensure_company_field(db: Session, field_key: str,
                         display_name: Optional[str] = None,
                         data_type: str = "text") -> bool:
    """确保 company 的 field_key 字段在 field_metadata 中存在(enabled)。

    不存在则自动创建(幂等, 防止重复); 返回是否新建。字段已存在则不动。
    """
    field_key = field_key.strip()
    if not field_key:
        return False
    exists = db.execute(
        select(FieldMetadata).where(
            FieldMetadata.entity_type == "company",
            FieldMetadata.field_key == field_key,
            FieldMetadata.is_deleted == False,
        ).limit(1)
    ).scalar_one_or_none()
    if exists:
        return False
    label = display_name or _DYNAMIC_FIELD_LABELS.get(field_key) or field_key
    dtype = _DYNAMIC_FIELD_TYPES.get(field_key, data_type)
    # 用纯 SQL 插入(避免依赖 BaseModel 自动生成 id 等)
    new_field = FieldMetadata(
        entity_type="company",
        field_key=field_key,
        display_name=label,
        data_type=dtype,
        group_name="联系信息",
        is_list_visible=True,
        is_searchable=False,
        is_filterable=False,
        is_exportable=True,
        status="enabled",
    )
    db.add(new_field)
    db.flush()
    logger.info("动态创建 company 字段: %s (%s)", field_key, label)
    return True
