from typing import Optional
import datetime
from sqlalchemy import String, Date, BigInteger, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Person(BaseModel):
    """人员主表 — 独立维度实体"""
    __tablename__ = "person"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="人员编码")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="姓名")
    email: Mapped[Optional[str]] = mapped_column(String(256), default=None, comment="邮箱")
    phone: Mapped[Optional[str]] = mapped_column(String(32), default=None, comment="电话")
    department_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="所属部门ID")
    company_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="所属单位ID")
    position: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="职位")
    status: Mapped[str] = mapped_column(String(32), default="active", comment="在职状态")
    entry_date: Mapped[Optional[datetime.date]] = mapped_column(Date, default=None, comment="入职日期")
    resign_date: Mapped[Optional[datetime.date]] = mapped_column(Date, default=None, comment="离职日期")
    ext_attrs: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="动态扩展字段")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="是否启用")
