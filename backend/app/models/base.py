from typing import Optional
import datetime
from sqlalchemy import Boolean, BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TimestampMixin:
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, comment="create time"
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
        comment="update time",
    )


class SoftDeleteMixin:
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="soft delete flag"
    )


class BaseModel(Base, TimestampMixin, SoftDeleteMixin):
    __abstract__ = True
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="primary key"
    )
