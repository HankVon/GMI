"""项目跟踪线索关联 — 意向/招标/中标/施工线索归整到项目, 支持自动监控各阶段。"""
from typing import Optional
import datetime
from decimal import Decimal
from sqlalchemy import String, Boolean, BigInteger, DateTime, Text, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProjectClue(Base):
    """线索→项目 持久化关联(自动匹配, 防张冠李戴)。

    每(project_id, clue_type, clue_id) 唯一; 匹配置信度 + 依据可追溯。
    """

    __tablename__ = "project_clue"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="项目ID")
    clue_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="intent/web_clue/bid")
    clue_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="线索表主键")
    stage: Mapped[str] = mapped_column(String(32), default="", comment="investment/bidding/awarded/construction")
    title: Mapped[Optional[str]] = mapped_column(String(512), default="", comment="线索标题")
    url: Mapped[Optional[str]] = mapped_column(String(1024), default="", comment="原文URL")
    source_name: Mapped[Optional[str]] = mapped_column(String(128), default="", comment="来源名称")
    region: Mapped[Optional[str]] = mapped_column(String(128), default="", comment="地域")
    purchaser: Mapped[Optional[str]] = mapped_column(String(255), default="", comment="采购人/业主单位")
    published_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, default=None, comment="实际发布时间")
    fetched_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, default=None, comment="抓取时间")
    confidence: Mapped[float] = mapped_column(Numeric(4, 2), default=0, comment="关联置信度0~1")
    match_reason: Mapped[Optional[str]] = mapped_column(String(255), default="", comment="匹配依据")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已读")

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="soft delete flag")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
