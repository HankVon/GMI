from typing import Optional
import datetime
from sqlalchemy import String, BigInteger, DateTime, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ProjectMember(BaseModel):
    """项目-人员关联表(弱关联核心,保留历史轨迹)"""
    __tablename__ = "project_member"

    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="项目ID")
    person_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="人员ID")
    role: Mapped[str] = mapped_column(String(64), nullable=False, comment="项目角色")
    responsibility: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="职责描述")
    stage: Mapped[str] = mapped_column(String(64), default="", comment="所属阶段(关联 option_set:project_progress_stage, 空=全程/不限)")
    joined_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment="加入时间")
    left_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, default=None, comment="退出时间")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否在职")
    ext_attrs: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="动态扩展字段")
