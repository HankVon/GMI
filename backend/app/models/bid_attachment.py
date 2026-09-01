"""标讯附件 — 招标文件/公告附件(替代 meta.attachments JSON, 支持后台管理)"""
from typing import Optional
import datetime
from sqlalchemy import String, BigInteger, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BidAttachment(Base):
    """标讯附件: 上传的本地文件或远程抓取的文件。"""

    __tablename__ = "bid_attachment"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="primary key")
    bid_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="标讯 id")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="附件名")
    local_path: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="uploads/ 相对路径")
    remote_url: Mapped[Optional[str]] = mapped_column(String(1024), default=None, comment="远程抓取 URL")
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, comment="文件大小(字节)")
    file_type: Mapped[Optional[str]] = mapped_column(String(32), default=None, comment="文件类型 pdf/docx/xlsx/zip")
    remark: Mapped[Optional[str]] = mapped_column(String(255), default=None, comment="备注")
    uploaded_by: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="上传人 user_id")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, comment="create time")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, comment="update time"
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="soft delete flag")
