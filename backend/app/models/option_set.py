from typing import Optional
from sqlalchemy import String, Integer, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class OptionSet(BaseModel):
    """选项集主表"""
    __tablename__ = "option_set"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="选项集编码")
    name: Mapped[str] = mapped_column(String(256), nullable=False, comment="选项集名称")
    description: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="描述")


class OptionItem(BaseModel):
    """选项项表"""
    __tablename__ = "option_item"

    option_set_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="选项集ID")
    value: Mapped[str] = mapped_column(String(128), nullable=False, comment="选项值")
    label: Mapped[str] = mapped_column(String(256), nullable=False, comment="显示标签")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    color: Mapped[Optional[str]] = mapped_column(String(32), default=None, comment="颜色标记")
