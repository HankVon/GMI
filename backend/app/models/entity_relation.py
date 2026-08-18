"""知识抽取三元组模型 — 开放域关系落库(Neo4j 降级查询用)。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class EntityRelation(BaseModel):
    __tablename__ = "entity_relation"

    source_type: Mapped[str] = mapped_column(String(32), comment="源实体类型 company/person/project/region")
    source_name: Mapped[str] = mapped_column(String(512), comment="源实体名称")
    source_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, default=None, comment="源实体id")
    target_type: Mapped[str] = mapped_column(String(32), comment="目标实体类型")
    target_name: Mapped[str] = mapped_column(String(512), comment="目标实体名称")
    target_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, default=None, comment="目标实体id")
    relation: Mapped[str] = mapped_column(String(64), comment="关系标识(开放)")
    relation_zh: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="关系中文名")
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0.8"), comment="置信度 0-1")
    evidence: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True, comment="证据(原文句子)")
    source_text_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, default=None, comment="来源文本id")
