from typing import Optional
import datetime
from sqlalchemy import String, BigInteger, DateTime, Boolean, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ProjectProgress(BaseModel):
    """项目进展记录（手动维护，支持排序，不依赖字段变更历史）"""
    __tablename__ = "project_progress"

    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="项目ID")
    title: Mapped[str] = mapped_column(String(256), nullable=False, comment="进展标题")
    content: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="进展详情")
    progress_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment="进展日期")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序权重(越小越靠前)")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="软删除")
