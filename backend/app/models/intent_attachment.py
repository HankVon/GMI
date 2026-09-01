"""意向公告附件 — 爬取的公告附件(pdf/doc/xls 等)。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class IntentAttachment(BaseModel):
    __tablename__ = "intent_attachment"

    intent_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="意向 id")
    file_name: Mapped[str] = mapped_column(String(255), comment="文件名")
    local_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="相对存储路径 uploads/...")
    remote_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True, comment="原网页附件地址")
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, comment="文件大小(字节)")
