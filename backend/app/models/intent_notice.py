"""意向性项目信息模型 — 政务源抓取的结构化意向(提前获取招标)。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class IntentNotice(BaseModel):
    __tablename__ = "intent_notice"

    clue_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="来源线索id")
    source_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="来源id")
    title: Mapped[str] = mapped_column(String(512), comment="标题")
    url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True, comment="原文链接")
    dept: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="发布部门")
    project_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="项目类型")
    industry: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="行业")
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True, comment="预算金额(万元)")
    region: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="地域")
    province: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    county: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    contact: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="联系人/电话")
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="拟开工时间")
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="发布时间")
    status: Mapped[str] = mapped_column(String(32), default="new", comment="状态 new/qualified/skip/expired")
    keywords: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="命中关键词")
    matched_entity: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="匹配人脉实体JSON")
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="原文摘要")
