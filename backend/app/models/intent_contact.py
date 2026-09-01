"""意向联系人 — 后台录入的甲方/设计师/建造商/分包 分组联系人。

前台公开接口仅返回脱敏占位(姓名/电话等用 **** 掩码), 后台管理接口返回真实信息。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class IntentContact(BaseModel):
    __tablename__ = "intent_contact"

    intent_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="意向 id")
    group: Mapped[str] = mapped_column(String(32), default="甲方", comment="分组: 甲方/设计师/建造商/分包")
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="姓名")
    role: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="职务")
    department: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="部门")
    position: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="职位")
    phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="电话")
    mobile: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="手机")
    address: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="地址")
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="备注")
    sort_order: Mapped[int] = mapped_column(BigInteger, default=0, comment="排序(升序)")
