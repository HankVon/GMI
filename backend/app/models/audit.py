from typing import Optional
import datetime
from sqlalchemy import String, BigInteger, JSON, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    """操作审计日志表(不继承BaseModel,独立字段)"""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="操作用户ID")
    username: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="操作用户名(快照)")
    action: Mapped[str] = mapped_column(String(64), nullable=False, comment="操作类型")
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="资源类型")
    resource_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="资源ID")
    resource_name: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="资源名称(快照)")
    detail: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="操作详情JSON")
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="客户端IP")
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="User-Agent")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, comment="操作时间"
    )


class FieldChangeHistory(Base):
    """字段值变更历史表"""
    __tablename__ = "field_change_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="实体类型")
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="实体实例ID")
    field_key: Mapped[str] = mapped_column(String(128), nullable=False, comment="字段标识")
    field_label: Mapped[Optional[str]] = mapped_column(String(256), default=None, comment="字段显示名")
    old_value: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="旧值")
    new_value: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="新值")
    changed_by: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="变更人ID")
    changed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, comment="变更时间"
    )
