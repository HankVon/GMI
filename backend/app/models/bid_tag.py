"""标讯标签 — 规则标签定义 + 标讯-标签关联

前台详情页头部标签(五色)可由:
  - 服务端规则合成(notice_type / industry / 截止倒计时)
  - 本模块: 运营手工打标 或 关键字规则自动打标
"""
from typing import Optional
import datetime
from sqlalchemy import String, BigInteger, DateTime, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BidTagDef(Base):
    """标签字典定义。"""

    __tablename__ = "bid_tag_def"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="primary key")
    label: Mapped[str] = mapped_column(String(64), nullable=False, comment="标签文本")
    kind: Mapped[str] = mapped_column(
        String(16), default="category", comment="展示样式: status/category/warning/danger/plain"
    )
    rule_keyword: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="自动打标关键字(逗号分隔)")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, comment="create time")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, comment="update time"
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="soft delete flag")


class BidNoticeTag(Base):
    """标讯-标签关联。"""

    __tablename__ = "bid_notice_tag"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="primary key")
    bid_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="标讯 id")
    tag_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="标签 id")
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="打标人 user_id")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, comment="create time")
