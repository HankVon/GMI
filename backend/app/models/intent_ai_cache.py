"""意向 AI 研判结果缓存 — 按意向唯一, 用于复用已生成的分析(避免每次点击重复生成)。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class IntentAiCache(BaseModel):
    __tablename__ = "intent_ai_cache"

    intent_id: Mapped[int] = mapped_column(BigInteger, unique=True, comment="意向 id")
    source: Mapped[str] = mapped_column(String(16), default="llm", comment="来源: llm/rule")
    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="生成模型名")
    analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="分析结果 JSON")
    note: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="说明")
