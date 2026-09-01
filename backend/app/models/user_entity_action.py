"""用户对标讯的监控与收藏状态。"""
from sqlalchemy import BigInteger, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class UserEntityAction(BaseModel):
    __tablename__ = "user_entity_action"
    __table_args__ = (UniqueConstraint("user_id", "entity_type", "entity_id", name="uq_user_entity_action"),)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    entity_type: Mapped[str] = mapped_column(nullable=False)
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    monitored: Mapped[bool] = mapped_column(Boolean, default=False)
    collected: Mapped[bool] = mapped_column(Boolean, default=False)
