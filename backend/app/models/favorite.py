"""收藏与标签模型 — 对标建设通收藏 / 竞争跟踪(A4 / B1)。

- favorite: 用户 × 实体类型 × 实体ID(幂等唯一), 收藏即插入, 取消即删除
- tag: 用户个人标签, 同一实体可挂多个标签

对应指导文档: docs/gmi-renovation-guide.md A4 / B1
"""
from __future__ import annotations

from sqlalchemy import BigInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Favorite(BaseModel):
    __tablename__ = "favorite"
    __table_args__ = (
        UniqueConstraint("user_id", "entity_type", "entity_id", name="uk_favorite_user_entity"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="用户ID")
    entity_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="实体类型: company/project/person"
    )
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="实体ID")


class Tag(BaseModel):
    __tablename__ = "tag"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "entity_type", "entity_id", "tag", name="uk_tag_user_entity"
        ),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="用户ID")
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="实体类型")
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="实体ID")
    tag: Mapped[str] = mapped_column(String(64), nullable=False, comment="标签文本")
