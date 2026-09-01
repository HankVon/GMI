"""行业数据标准库模型 — 对标建设通分项查询的 6 个标准数据域。

溯源约定:
  - 所有来自公共渠道的数据必须带 source(来源名) + source_url(原文链接)
    + published_at(采集/公示时间), 支撑"信息来源"列与免责声明。
  - status/valid_to 支撑"失效预警"类运营功能。

对应指导文档: docs/gmi-renovation-guide.md A1 / B1
"""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Qualification(BaseModel):
    """单位资质台账 — 类别三段式(类别_细分_等级), 含发证机关/有效期/状态。"""
    __tablename__ = "qualification"

    company_id: Mapped[int] = mapped_column(BigInteger, comment="单位id")
    category: Mapped[str] = mapped_column(String(64), comment="资质大类(施工/勘察/设计/监理等)")
    professional: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="专业/细分(可空)")
    level: Mapped[str] = mapped_column(String(32), comment="等级(甲/乙/丙/一级/二级/三级/不分等级)")
    issue_org: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="发证机关")
    cert_no: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="证书编号")
    valid_from: Mapped[Optional[date]] = mapped_column(Date, default=None, comment="发证日期/有效期起")
    valid_to: Mapped[Optional[date]] = mapped_column(Date, default=None, comment="有效期至")
    status: Mapped[str] = mapped_column(String(16), default="active", comment="active/expiring/expired")
    source: Mapped[str] = mapped_column(String(64), default="manual", comment="来源 manual/import/sihku/...")
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), default=None, comment="来源链接")
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None, comment="采集/公示时间")


class Honor(BaseModel):
    """单位荣誉台账 — 奖项名/等级/授予机关/日期, 公开+敏感分级脱敏。"""
    __tablename__ = "honor"

    company_id: Mapped[int] = mapped_column(BigInteger, comment="单位id")
    person_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="关联人员id(荣誉可挂到人)")
    title: Mapped[str] = mapped_column(String(512), comment="荣誉标题")
    level: Mapped[Optional[str]] = mapped_column(String(32), default=None, comment="等级(国家级/省/市/行业等)")
    org: Mapped[Optional[str]] = mapped_column(String(256), default=None, comment="授予机关/组织")
    honored_at: Mapped[Optional[date]] = mapped_column(Date, default=None, comment="获奖日期")
    source: Mapped[str] = mapped_column(String(64), default="manual", comment="来源")
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), default=None, comment="来源链接")
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None, comment="采集/公示时间")


class CreditRecord(BaseModel):
    """单位诚信/不良行为记录 — 事由/机关/日期, 对接双随机一公开公示。"""
    __tablename__ = "credit_record"

    company_id: Mapped[int] = mapped_column(BigInteger, comment="单位id")
    title: Mapped[str] = mapped_column(String(512), comment="记录标题/事由摘要")
    reason: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="违规事由全文")
    org: Mapped[Optional[str]] = mapped_column(String(256), default=None, comment="公示机关")
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None, comment="公示日期")
    source: Mapped[str] = mapped_column(String(64), default="manual", comment="来源")
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), default=None, comment="来源链接")


class PersonCert(BaseModel):
    """人员证书 — 类别/证书号/印章号/有效期, 复用 person + person_skill。"""
    __tablename__ = "person_cert"

    person_id: Mapped[int] = mapped_column(BigInteger, comment="人员id")
    cert_type: Mapped[str] = mapped_column(String(64), comment="证书类型(建造师/监理/安全C证/职称/造价等)")
    cert_no: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="证书编号")
    seal_no: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="执业印章号")
    major: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="专业/注册类别")
    valid_from: Mapped[Optional[date]] = mapped_column(Date, default=None, comment="有效期起")
    valid_to: Mapped[Optional[date]] = mapped_column(Date, default=None, comment="有效期至")
    status: Mapped[str] = mapped_column(String(16), default="active", comment="active/expiring/expired")
    source: Mapped[str] = mapped_column(String(32), default="manual", comment="manual/import/external")


class CompanyIc(BaseModel):
    """单位工商信息 — 法人/资本/股东/分支/投资/变更(JSON 结构化)。"""
    __tablename__ = "company_ic"

    company_id: Mapped[int] = mapped_column(BigInteger, comment="单位id")
    legal_rep: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="法定代表人")
    registered_capital: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="注册资本(原文, 含币种)")
    est_date: Mapped[Optional[date]] = mapped_column(Date, default=None, comment="成立日期")
    shareholders: Mapped[Optional[list]] = mapped_column(JSON, default=None, comment="股东结构[{name,ratio,amount}]")
    branches: Mapped[Optional[list]] = mapped_column(JSON, default=None, comment="分支机构[{name,address}]")
    investments: Mapped[Optional[list]] = mapped_column(JSON, default=None, comment="对外投资[{name,ratio,amount}]")
    changes: Mapped[Optional[list]] = mapped_column(JSON, default=None, comment="变更记录[{date,item,from,to}]")
    source: Mapped[str] = mapped_column(String(64), default="manual", comment="来源 qcc/vendor/manual")
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), default=None, comment="来源链接")
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None, comment="抓取时间")


class CompanyLegalRisk(BaseModel):
    """单位司法与经营风险 — 裁判文书/被执行/处罚/经营异常等。"""
    __tablename__ = "company_legal_risk"

    company_id: Mapped[int] = mapped_column(BigInteger, comment="单位id")
    risk_type: Mapped[str] = mapped_column(String(32), comment="类型: lawsuit/judgment/executed/penalty/abnormal/pledge/...")
    title: Mapped[str] = mapped_column(String(512), comment="风险标题")
    court: Mapped[Optional[str]] = mapped_column(String(256), default=None, comment="法院/机关")
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), default=None, comment="涉案金额")
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None, comment="发布日期")
    source: Mapped[str] = mapped_column(String(64), default="manual", comment="来源")
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), default=None, comment="来源链接")


class BidOpenRecord(BaseModel):
    """开标记录 — 投标单位×场次, 支持同场竞标分析(COMPETES_WITH)。"""
    __tablename__ = "bid_open_record"

    bid_notice_id: Mapped[int] = mapped_column(BigInteger, comment="关联 bid_notice.id(一场一公告)")
    company_id: Mapped[int] = mapped_column(BigInteger, comment="投标单位id")
    role: Mapped[str] = mapped_column(String(32), default="bidder", comment="角色 bidder/winner(中标)")
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), default=None, comment="投标报价")
    discount_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), default=None, comment="下浮率(小数值, 如 0.05=5%)")
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None, comment="开标时间")
