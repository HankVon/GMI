"""内容工厂 ORM — 发布渠道 / 内容资产"""
from typing import Optional
import datetime
from sqlalchemy import String, Boolean, BigInteger, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ContentChannel(Base):
    """发布渠道: 官网/公众号/知乎/百家号等"""

    __tablename__ = "content_channel"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="primary key")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="渠道名称")
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="渠道编码")
    url_prefix: Mapped[Optional[str]] = mapped_column(String(1024), default=None, comment="发布URL前缀")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, comment="create time")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, comment="update time"
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="soft delete flag")


class ContentAsset(Base):
    """内容资产: 智能体生成的内容(报告/FAQ/公司档案/文章), 走 草稿→审核→发布"""

    __tablename__ = "content_asset"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="primary key")
    title: Mapped[str] = mapped_column(String(512), nullable=False, comment="内容标题")
    kind: Mapped[str] = mapped_column(String(32), default="article",
                                      comment="类型: industry_report/faq/company_profile/article")
    channel: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="目标渠道编码")
    channel_name: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="渠道名称快照")
    summary: Mapped[Optional[str]] = mapped_column(String(1024), default=None, comment="摘要(用于分发)")
    content: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="正文(Markdown)")
    source_data: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="生成依据的数据统计JSON")
    status: Mapped[str] = mapped_column(String(16), default="draft",
                                        comment="状态: draft/review/published/rejected")
    review_comment: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="审核意见")
    published_url: Mapped[Optional[str]] = mapped_column(String(1024), default=None, comment="发布URL(模拟)")
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="创建人id(智能体=0)")
    created_by_name: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="创建人名称")
    geo_feedback: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="GEO反馈(回链geo_mention)")
    published_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, default=None, comment="发布时间")

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, comment="create time")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, comment="update time"
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="soft delete flag")
