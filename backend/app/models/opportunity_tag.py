"""商机标签关联 — 一个商机关联多个策展标签(热点领域/热门项目)。"""
from sqlalchemy import BigInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class OpportunityTag(BaseModel):
    """商机 ↔ 策展标签 多对多关联。"""
    __tablename__ = "opportunity_tag"
    __table_args__ = (UniqueConstraint("opportunity_id", "tag_id", name="uq_opportunity_tag"),)

    opportunity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tag_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="关联 opportunity_tag_def.id")
    tag_kind: Mapped[str] = mapped_column(String(32), default="hot_project", comment="tag 类别: hot_field/hot_project")


class OpportunityTagDef(BaseModel):
    """策展标签字典 — 运营维护的标签候选集(热点领域/热门项目)。"""
    __tablename__ = "opportunity_tag_def"

    code: Mapped[str] = mapped_column(String(64), nullable=False, comment="标签代码, 唯一")
    label: Mapped[str] = mapped_column(String(64), nullable=False, comment="标签显示名")
    kind: Mapped[str] = mapped_column(String(32), default="hot_project", comment="hot_field/hot_project")
    is_new: Mapped[bool] = mapped_column(default=True, comment="是否展示 NEW 徽标")
    sort_order: Mapped[int] = mapped_column(BigInteger, default=0)