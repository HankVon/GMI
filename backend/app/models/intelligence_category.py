"""情报分类字典 — 行业/项目类型/阶段/数据集 四类目录(录入表单下拉/筛选区/统计分组)。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class IntelligenceCategory(BaseModel):
    __tablename__ = "intelligence_category"

    category: Mapped[str] = mapped_column(String(32), comment="分类维度: industry/project_type/stage/dataset")
    code: Mapped[str] = mapped_column(String(64), comment="编码")
    label: Mapped[str] = mapped_column(String(128), comment="显示名")
    parent_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="父分类id(树形)")
    sort_order: Mapped[int] = mapped_column(BigInteger, default=0, comment="排序")
    enabled: Mapped[int] = mapped_column(BigInteger, default=1, comment="启用 1/0")
