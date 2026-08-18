"""人脉库模型 — 人员专长/人脉边/招标匹配(可扩展, 聚合视图)。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class PersonSkill(BaseModel):
    __tablename__ = "person_skill"

    person_id: Mapped[int] = mapped_column(BigInteger, comment="人员id")
    skill: Mapped[str] = mapped_column(String(128), comment="专长/技能标签")
    source: Mapped[str] = mapped_column(String(32), default="manual", comment="来源 manual/project_infer/category")
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0.8"), comment="置信度")


class NetworkEdge(BaseModel):
    __tablename__ = "network_edge"

    src_type: Mapped[str] = mapped_column(String(32), comment="源类型 person/company/project")
    src_id: Mapped[int] = mapped_column(BigInteger, comment="源实体id")
    src_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    tgt_type: Mapped[str] = mapped_column(String(32), comment="目标类型")
    tgt_id: Mapped[int] = mapped_column(BigInteger)
    tgt_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    rel_type: Mapped[str] = mapped_column(String(64), comment="关系类型")
    rel_zh: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("1.0"), comment="权重")
    source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="来源")
    evidence: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True, comment="证据")
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="最近出现")


class TenderMatch(BaseModel):
    __tablename__ = "tender_match"

    clue_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="招标/意向线索id")
    intent_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="意向通知id(预留)")
    title: Mapped[str] = mapped_column(String(512), comment="招标/意向标题")
    entity_type: Mapped[str] = mapped_column(String(32), comment="匹配实体类型 person/company")
    entity_id: Mapped[int] = mapped_column(BigInteger)
    entity_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    match_type: Mapped[str] = mapped_column(String(32), default="skill", comment="匹配方式")
    match_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    score: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0"), comment="匹配得分")
    region: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    amount: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="new", comment="状态 new/contacted/followed/ignored")
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="推荐有效期截止(超期自动标记过期)")
    is_expired: Mapped[bool] = mapped_column(default=False, comment="是否已过期(定时任务维护)")
