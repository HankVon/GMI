"""商机版本记录 — 每次人工调研更新迭代一条新版本。"""
from typing import Optional
import datetime
from sqlalchemy import String, BigInteger, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class OpportunityVersion(BaseModel):
    """商机版本快照: 每条记录对应一次人工更新, 详情页展示历史变更。"""
    __tablename__ = "opportunity_version"

    opportunity_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="关联商机 id")
    version: Mapped[str] = mapped_column(String(32), nullable=False, comment="版本号 V2.0 / V2.0.3 / V3.2.3")
    change_summary: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="变更摘要")
    operator: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="操作人")
    released_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, comment="发布时间")