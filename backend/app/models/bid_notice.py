"""中标公告 — 从 web_clue 中标公告解析出的结构化数据。

与 web_clue 解耦: web_clue 是原始线索, bid_notice 是解析后的中标关系
(采购人 / 中标供应商 / 金额 / 时间), 用于人脉网络与关联分析。

后台管理扩展(Phase 1):
- 生命周期状态机 status: draft→pending→approved→published / offline, rejected
- 后台录入字段: category/industry/purchase_way/price_type/budget_min/budget_max
- 审核/发布留痕: submitted_by/reviewed_by/publish_by 等操作人字段
"""
from typing import Optional
import datetime
from decimal import Decimal
from sqlalchemy import String, Boolean, BigInteger, DateTime, Text, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# 标讯生命周期状态(与前台可见性联动)
BID_STATUS_DRAFT = "draft"          # 草稿: 编辑录入中, 前台不可见
BID_STATUS_PENDING = "pending"      # 待审核: 已提交, 等待审核员审核
BID_STATUS_APPROVED = "approved"    # 已审核: 审核通过, 可发布
BID_STATUS_REJECTED = "rejected"    # 已驳回: 审核未通过, 可编辑后重新提交
BID_STATUS_PUBLISHED = "published"  # 已发布: 前台可见
BID_STATUS_OFFLINE = "offline"      # 已下线: 前台不可见

BID_STATUS_LIST = [
    BID_STATUS_DRAFT, BID_STATUS_PENDING, BID_STATUS_APPROVED,
    BID_STATUS_REJECTED, BID_STATUS_PUBLISHED, BID_STATUS_OFFLINE,
]


class BidNotice(Base):
    """中标公告: 采购人(业主) → 中标供应商 的关系数据。

    每条公告可能有多家中标供应商, 用 meta.suppliers 数组存储:
      [{supplier, supplier_company_id, amount, address}]
    purchaser_company_id / supplier_company_id 按名称匹配 company 表(可空, 未匹配为 None)。

    前台可见性规则: status == 'published' 且 is_deleted == False。
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

    notice_type: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="公告类型(中标/成交/招标)")
    agency: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="采购代理机构名称")
    source_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="来源站点 id(web_source)")
    source_name: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="来源名称")

    published_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, default=None, comment="公告发布时间(原始采集时间)")
    fetched_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, comment="解析时间")

    # ── 后台管理: 生命周期状态 ──
    status: Mapped[str] = mapped_column(
        String(32), default=BID_STATUS_PUBLISHED, comment="生命周期状态:draft/pending/approved/rejected/published/offline"
    )

    # ── 后台管理: 分类/筛选维度字段(前台标签云数据源) ──
    category: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="项目分类(工程/服务/货物)")
    industry: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="行业类型(20项, option_set:bid_industry)")
    purchase_way: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="采购方式(公开招标/邀请招标/竞争性谈判/单一来源/询价/其他)")
    price_type: Mapped[Optional[str]] = mapped_column(String(32), default=None, comment="询价方式(单价/总价)")
    budget_min: Mapped[Optional[float]] = mapped_column(Float, default=None, comment="预算金额下限(万元)")
    budget_max: Mapped[Optional[float]] = mapped_column(Float, default=None, comment="预算金额上限(万元)")

    # ── 后台管理: 审核 / 发布留痕 ──
    submitted_by: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="提交人 user_id")
    submitted_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, default=None, comment="提交审核时间")
    reviewed_by: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="审核人 user_id")
    reviewed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, default=None, comment="审核时间")
    review_comment: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="审核意见")
    publish_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, default=None, comment="后台实际发布时间")
    publish_by: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="发布人 user_id")

    # ── 后台管理: 创建/编辑留痕 ──
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="创建人 user_id(后台录入)")
    updated_by: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="最后编辑人 user_id")

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, comment="create time")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, comment="update time"
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="soft delete flag")
