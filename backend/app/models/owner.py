"""业主画像主表 — 业主维度聚合(用于业主概览看板/业主专查检索)。

商机详情所属业主可关联到这张表, 便于人脉网络聚合与单位级看板。
"""
from typing import Optional
from sqlalchemy import String, BigInteger, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Owner(BaseModel):
    """业主单位主表。"""
    __tablename__ = "owner"

    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="业主名称")
    owner_type: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="业主类型")
    owner_scale: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="业主规模")
    province: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    city: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    industry: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="所属行业")
    opportunity_count: Mapped[int] = mapped_column(BigInteger, default=0, comment="关联商机数")
    total_amount_wan: Mapped[int] = mapped_column(BigInteger, default=0, comment="累计投资金额(万元)")