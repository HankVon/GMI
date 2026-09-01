"""商机主表 — 人工策展的项目商机(立项阶段前期项目)。

与 bid_notice(招标阶段公告) 互为补充: 商机偏立项/可投资的前期线索,
通过人工调研 + 版本跟踪持续维护。每条商机关联 1~N 个策展标签(热点领域/热门项目),
记录最新版本号, 详情页展示完整版本历史。
"""
from typing import Optional
import datetime
from sqlalchemy import String, BigInteger, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Opportunity(BaseModel):
    """项目商机主表。"""
    __tablename__ = "opportunity"

    project_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="项目名称")
    owner_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="业主/建设单位")
    owner_type: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="业主类型: 国央企/民企/机关单位/事业单位/外资")
    owner_scale: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="业主规模: 大型/中型/小型")
    amount_wan: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="投资金额(万元)")
    stage: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="项目阶段")
    region_province: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="省")
    region_city: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="市")
    project_type: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="项目类型")
    unit_role: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="我方角色")
    unit_name: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="我方单位名称")
    contact_summary: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="关键联系人(整体设闸)")
    followup_log: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="跟进记录(整体设闸)")
    body_excerpt: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="项目摘要")
    current_version: Mapped[Optional[str]] = mapped_column(String(32), default=None, comment="当前版本号")
    dataset_type: Mapped[str] = mapped_column(String(32), default="project", comment="数据集: project/proposed/landTrade")
    source: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="数据来源")
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, comment="更新时间")
    published_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, default=None, comment="首版发布时间")