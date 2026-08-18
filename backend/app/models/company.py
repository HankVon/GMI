"""Company and ProjectCompany ORM models"""
from typing import Optional
import datetime
from sqlalchemy import String, BigInteger, DateTime, Boolean, JSON, Date
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Company(BaseModel):
    """单位主表 — 商机来源 + 人脉依附的共同地基"""
    __tablename__ = "company"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="单位编码")
    name: Mapped[str] = mapped_column(String(256), nullable=False, comment="单位名称")
    short_name: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="简称")
    company_type: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="单位类型(关联 option_set:company_type)")
    province: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="省份")
    city: Mapped[Optional[str]] = mapped_column(String(64), default=None, comment="城市")
    industry: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="行业")
    credit_code: Mapped[Optional[str]] = mapped_column(String(64), default=None, unique=True, comment="统一社会信用代码")
    credit_level: Mapped[Optional[str]] = mapped_column(String(32), default=None, comment="信用等级")
    website: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="官网")
    address: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="地址")
    ext_attrs: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="动态扩展字段")


class ProjectCompany(BaseModel):
    """项目-单位关联表(弱关联,保留历史轨迹)"""
    __tablename__ = "project_company"

    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="项目ID")
    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="单位ID")
    role: Mapped[str] = mapped_column(String(64), nullable=False, comment="角色(关联 option_set:project_company_role)")
    stage: Mapped[str] = mapped_column(String(64), default="", comment="所属阶段(关联 option_set:project_progress_stage, 空=全程/不限)")
    joined_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment="参与时间")
    left_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, default=None, comment="退出时间")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否参与中")
    ext_attrs: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment="动态扩展字段")
