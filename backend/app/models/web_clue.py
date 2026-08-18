"""网页线索 — crawl4ai 抓取后经筛选入库的线索记录"""
from typing import Optional
import datetime
from sqlalchemy import String, Boolean, BigInteger, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WebClue(Base):
    """网页线索: 只有通过筛选(域名白名单 + 关键词/地域)的网页才会入库。

    未通过筛选的网页直接丢弃, 不创建记录 → 不会进入系统列表。
    """

    __tablename__ = "web_clue"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="primary key")
    url: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True, comment="网页 URL(唯一)")
    title: Mapped[str] = mapped_column(String(512), nullable=False, comment="网页标题")
    summary: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="摘要")
    content: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="正文(Markdown)")
    source_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="来源站点 ID(web_source)")
    source_name: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="来源名称快照")

    # 筛选结果
    hit_keywords: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="命中的关键词(逗号分隔)")
    region: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="命中的地域")
    category: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="分类(如:矿业/基建/项目)")

    # 状态: pending待入库 / accepted已通过 / rejected已拒绝 / imported已转实体
    status: Mapped[str] = mapped_column(String(32), default="accepted", comment="线索状态")

    published_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, default=None, comment="网页发布时间")
    fetched_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, comment="抓取时间")

    # 冗余字段(便于后续一键转成公司/项目/人员)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="扩展信息(提取结果)")

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, comment="create time")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, comment="update time"
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="soft delete flag")
