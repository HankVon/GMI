"""意向性项目信息模型 — 政务源抓取的结构化意向(提前获取招标)。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import JSON, BigInteger, DateTime, Numeric, String, Text, func
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

    # ── 情报中心后台管理扩展(审核发布/分类展示) ──
    wf_status: Mapped[str] = mapped_column(
        String(32), default="draft",
        comment="流转状态 draft/pending/approved/published/offline/rejected",
    )
    review_comment: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="审核意见")
    reviewer_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="审核人id")
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="审核时间")
    publisher_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="发布人id")
    offline_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="下架时间")
    stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="项目阶段 设计/动工/竣工/竣工验收")
    dataset_type: Mapped[str] = mapped_column(
        String(32), default="project", comment="数据集 project/proposed/landTrade",
    )
    ext_attrs: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="扩展字段JSON(工程地址/招标类型/资金来源/建筑规模/层数/建设性质/项目代码等)",
    )
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="创建人id")
