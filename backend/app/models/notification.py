"""站内通知表模型"""
from typing import Optional
from sqlalchemy import BigInteger, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Notification(BaseModel):
    """站内通知(sys_notification): 线索过期/项目进度变更/新中标等提醒"""
    __tablename__ = "sys_notification"

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="接收用户ID")
    type: Mapped[str] = mapped_column(String(32), default="system", comment="类型:clue_expire/progress/bid_new/contact/system")
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="标题")
    content: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="内容")
    related_type: Mapped[Optional[str]] = mapped_column(String(32), default=None, comment="关联实体类型")
    related_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="关联实体ID")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, comment="已读:0-否,1-是")
    status: Mapped[str] = mapped_column(String(16), default="pending", comment="处理状态:pending/processing/resolved/closed")
