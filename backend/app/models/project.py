from typing import Optional
import datetime
from sqlalchemy import String, Text, Date, BigInteger, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Project(BaseModel):
    """项目主表 — 中台核心实体"""
    __tablename__ = "project"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="项目编码")
    name: Mapped[str] = mapped_column(String(256), nullable=False, comment="项目名称")
    description: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="项目描述")
    status: Mapped[str] = mapped_column(String(32), default="active", comment="项目状态")
    manager_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="负责人ID(快照)")
    start_date: Mapped[Optional[datetime.date]] = mapped_column(Date, default=None, comment="启动日期")
    end_date: Mapped[Optional[datetime.date]] = mapped_column(Date, default=None, comment="预计结束日期")
    department_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="归属部门ID")
    ext_attrs: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="动态扩展字段")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")
