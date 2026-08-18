from pydantic import BaseModel, Field
from typing import Optional
import datetime


class FieldMetadataCreate(BaseModel):
    """创建字段元数据"""
    entity_type: str = Field(..., max_length=64, description="所属实体:project/person/project_member")
    field_key: str = Field(..., max_length=128, description="字段标识(英文)")
    display_name: str = Field(..., max_length=256, description="显示名")
    data_type: str = Field(..., max_length=32, description="数据类型:text/textarea/number/money/date/select/multi_select/switch/entity_ref")
    option_set_code: Optional[str] = None
    default_value: Optional[str] = None
    validation_rules: Optional[dict] = None
    sort_order: int = Field(default=0)
    group_name: Optional[str] = None
    is_required: bool = False
    is_list_visible: bool = True
    is_searchable: bool = False
    is_filterable: bool = False
    is_exportable: bool = True
    field_permissions: Optional[dict] = None  # {"view":["admin"],"edit":["admin","pm"]}
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    status: str = Field(default="enabled", max_length=32)


class FieldMetadataUpdate(BaseModel):
    """更新字段元数据(增量)"""
    display_name: Optional[str] = None
    data_type: Optional[str] = None
    option_set_code: Optional[str] = None
    validation_rules: Optional[dict] = None
    sort_order: Optional[int] = None
    group_name: Optional[str] = None
    is_required: Optional[bool] = None
    is_list_visible: Optional[bool] = None
    is_searchable: Optional[bool] = None
    is_filterable: Optional[bool] = None
    is_exportable: Optional[bool] = None
    field_permissions: Optional[dict] = None
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    status: Optional[str] = None


class FieldMetadataResponse(BaseModel):
    """字段元数据响应"""
    id: int
    entity_type: str
    field_key: str
    display_name: str
    data_type: str
    option_set_code: Optional[str] = None
    default_value: Optional[str] = None
    validation_rules: Optional[dict] = None
    sort_order: int
    group_name: Optional[str] = None
    is_required: bool
    is_list_visible: bool
    is_searchable: bool
    is_filterable: bool
    is_exportable: bool
    field_permissions: Optional[dict] = None
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}
