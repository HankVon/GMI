"""标讯审核记录 — 记录标讯生命周期内每次状态变更(提交/审核/发布/下线)。

与 audit_log 的区别: audit_log 是全局操作审计(中间件自动写, 不含业务语义),
本表是标讯审核流水的结构化记录(含 from_status/to_status/意见), 供审核追溯与详情页展示。
"""
from typing import Optional
import datetime
from sqlalchemy import String, BigInteger, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BidReviewRecord(Base):
    """标讯审核/发布记录表"""

    __tablename__ = "bid_review_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    bid_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="关联标讯 bid_notice.id")
    action: Mapped[str] = mapped_column(String(32), nullable=False, comment="操作: submit/approve/reject/publish/offline/revert")
    reviewer_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="操作人 user_id")
    reviewer_name: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="操作人姓名快照")
    comment: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="意见/说明")
    from_status: Mapped[Optional[str]] = mapped_column(String(32), default=None, comment="变更前状态")
    to_status: Mapped[Optional[str]] = mapped_column(String(32), default=None, comment="变更后状态")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, comment="操作时间"
    )
