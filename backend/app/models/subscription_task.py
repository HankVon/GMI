"""检索条件订阅快照。暂不包含会员或计费字段。"""
from typing import Optional
import datetime
from sqlalchemy import BigInteger, Boolean, JSON, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class SubscriptionTask(BaseModel):
    __tablename__ = "subscription_task"
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    condition_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, default=None)
    last_match_count: Mapped[int] = mapped_column(BigInteger, default=0)
    product_type: Mapped[str] = mapped_column(String(32), default="tender", comment="tender/opportunity")
