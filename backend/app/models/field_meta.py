from typing import Optional
import datetime
from sqlalchemy import String, JSON, Integer, Boolean, DateTime, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.database import Base


class FieldMetadata(BaseModel):
    """字段元数据表 — 动态字段引擎核心"""
    __tablename__ = "field_metadata"

    entity_type: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="所属实体:project/person/project_member"
    )
    field_key: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="字段标识(英文名)"
    )
    display_name: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="显示名"
    )
    data_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="数据类型:text/textarea/number/money/date/select/multi_select/switch/entity_ref"
    )
    option_set_code: Mapped[Optional[str]] = mapped_column(
        String(64), default=None, comment="关联选项集编码"
    )
    default_value: Mapped[Optional[str]] = mapped_column(
        String(512), default=None, comment="默认值"
    )
    validation_rules: Mapped[Optional[dict]] = mapped_column(
        JSON, default=None, comment="校验规则JSON"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, comment="排序"
    )
    group_name: Mapped[Optional[str]] = mapped_column(
        String(128), default=None, comment="分组名"
    )
    is_required: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否必填"
    )
    is_list_visible: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="列表展示"
    )
    is_searchable: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="可搜索"
    )
    is_filterable: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="可筛选"
    )
    is_exportable: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="可导出"
    )
    field_permissions: Mapped[Optional[dict]] = mapped_column(
        JSON, default=None, comment="字段级权限: {view:[role_codes], edit:[role_codes]}"
    )
    placeholder: Mapped[Optional[str]] = mapped_column(
        String(512), default=None, comment="输入提示"
    )
    help_text: Mapped[Optional[str]] = mapped_column(
        String(512), default=None, comment="帮助文本"
    )
    status: Mapped[str] = mapped_column(
        String(32), default="enabled", comment="状态:enabled/disabled"
    )


class FieldMetadataVersion(Base):
    """字段元数据版本表
    DDL 基础列: id / field_meta_id / version / snapshot / change_type / changed_by / changed_at
    不继承 BaseModel,避免 is_deleted/created_at/updated_at 列入(与 DDL 保持一致)
    """
    __tablename__ = "field_metadata_version"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键"
    )
    field_meta_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="字段元数据ID"
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="版本号"
    )
    snapshot: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="版本快照"
    )
    change_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="变更类型:create/update/delete"
    )
    changed_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, default=None, comment="变更人ID"
    )
    changed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, comment="变更时间"
    )
