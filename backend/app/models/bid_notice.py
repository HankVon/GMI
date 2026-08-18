"""中标公告 — 从 web_clue 中标公告解析出的结构化数据。

与 web_clue 解耦: web_clue 是原始线索, bid_notice 是解析后的中标关系
(采购人 / 中标供应商 / 金额 / 时间), 用于人脉网络与关联分析。
"""
from typing import Optional
import datetime
from sqlalchemy import String, Boolean, BigInteger, DateTime, Text, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BidNotice(Base):
    """中标公告: 采购人(业主) → 中标供应商 的关系数据。

    每条公告可能有多家中标供应商, 用 meta.suppliers 数组存储:
      [{supplier, supplier_company_id, amount, address}]
    purchaser_company_id / supplier_company_id 按名称匹配 company 表(可空, 未匹配为 None)。
    """

    __tablename__ = "bid_notice"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="primary key")
    clue_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="来源线索 web_clue.id")
    title: Mapped[str] = mapped_column(String(512), nullable=False, comment="公告标题")
    url: Mapped[Optional[str]] = mapped_column(String(1024), default=None, comment="公告链接")

    # 采购人(业主)
    purchaser: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="采购人/业主名称")
    purchaser_company_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="匹配的公司 id")
    region: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="采购区域(省)")

    # 中标供应商(数组存 meta)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="供应商明细[ {supplier, supplier_company_id, amount, address} ]")

    notice_type: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="公告类型(中标/成交)")
    agency: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="采购代理机构名称")
    source_name: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="来源名称")

    published_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, default=None, comment="公告发布时间")
    fetched_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, comment="解析时间")

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, comment="create time")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, comment="update time"
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="soft delete flag")
