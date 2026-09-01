"""标讯附件管理 API — 上传/列表/下载/删除。"""
import datetime
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.bid_notice import BidNotice
from app.models.bid_attachment import BidAttachment
from app.services.audit_service import log_action
from app.utils.upload_paths import upload_root

router = APIRouter(prefix="/admin/bids", tags=["标讯附件"])

_UPLOAD_ROOT = str(upload_root())
_ALLOWED_EXT = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar", ".7z", ".txt", ".jpg", ".jpeg", ".png"}


def _ensure_bid(db: Session, bid_id: int) -> BidNotice:
    bn = db.get(BidNotice, bid_id)
    if not bn or bn.is_deleted:
        raise HTTPException(status_code=404, detail="标讯不存在")
    return bn


def _att_dict(a: BidAttachment) -> dict:
    return {
        "id": a.id,
        "bid_id": a.bid_id,
        "file_name": a.file_name,
        "remote_url": a.remote_url,
        "file_size": a.file_size,
        "file_type": a.file_type,
        "remark": a.remark,
        "created_at": a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "",
    }


@router.get("/{bid_id}/attachments")
async def list_attachments(
    bid_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_view")),
):
    """标讯附件列表。"""
    _ensure_bid(db, bid_id)
    rows = db.execute(
        select(BidAttachment).where(
            BidAttachment.bid_id == bid_id, BidAttachment.is_deleted == False  # noqa: E712
        ).order_by(BidAttachment.id.desc())
    ).scalars().all()
    return {"success": True, "items": [_att_dict(r) for r in rows]}


@router.post("/{bid_id}/attachments")
async def upload_attachment(
    bid_id: int,
    file: UploadFile = File(...),
    remark: str = Query(""),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_edit")),
):
    """上传附件到 uploads/ 目录。"""
    _ensure_bid(db, bid_id)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(status_code=422, detail=f"不支持的文件类型: {ext or '无扩展名'}")
    safe_name = os.path.basename(file.filename or "attachment")
    subdir = f"bid/{bid_id}"
    os.makedirs(os.path.join(_UPLOAD_ROOT, subdir), exist_ok=True)
    stored_name = f"{datetime.datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}_{safe_name}"
    rel_path = os.path.join(subdir, stored_name)
    abs_path = os.path.join(_UPLOAD_ROOT, subdir, stored_name)
    content = await file.read()
    with open(abs_path, "wb") as f:
        f.write(content)
    att = BidAttachment(
        bid_id=bid_id,
        file_name=safe_name,
        local_path=rel_path,
        file_size=len(content),
        file_type=ext.lstrip(".") or None,
        remark=remark or None,
        uploaded_by=user.get("user_id"),
    )
    db.add(att)
    db.flush()
    log_action(db, user.get("user_id"), user.get("username") or user.get("display_name"),
               "bid_attachment_upload", "bid", bid_id, safe_name, {"file_size": len(content)})
    db.commit()
    db.refresh(att)
    return {"success": True, "data": _att_dict(att)}


@router.delete("/{bid_id}/attachments/{att_id}")
async def delete_attachment(
    bid_id: int,
    att_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_edit")),
):
    """删除附件(软删, 同时移除磁盘文件)。"""
    att = db.execute(
        select(BidAttachment).where(
            BidAttachment.id == att_id, BidAttachment.bid_id == bid_id,
            BidAttachment.is_deleted == False,  # noqa: E712
        )
    ).scalar_one_or_none()
    if not att:
        raise HTTPException(status_code=404, detail="附件不存在")
    att.is_deleted = True
    # 尽力删除磁盘文件(失败不阻塞)
    try:
        if att.local_path:
            abs_path = os.path.join(_UPLOAD_ROOT, att.local_path)
            if os.path.exists(abs_path):
                os.remove(abs_path)
    except OSError:  # noqa: BLE001
        pass
    log_action(db, user.get("user_id"), user.get("username") or user.get("display_name"),
               "bid_attachment_delete", "bid", bid_id, att.file_name)
    db.commit()
    return {"success": True}


@router.get("/{bid_id}/attachments/{att_id}/download")
async def download_attachment(
    bid_id: int,
    att_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_view")),
):
    """下载附件。"""
    att = db.execute(
        select(BidAttachment).where(
            BidAttachment.id == att_id, BidAttachment.bid_id == bid_id,
            BidAttachment.is_deleted == False,  # noqa: E712
        )
    ).scalar_one_or_none()
    if not att:
        raise HTTPException(status_code=404, detail="附件不存在")
    if att.local_path:
        abs_path = os.path.join(_UPLOAD_ROOT, att.local_path)
        if not os.path.exists(abs_path):
            raise HTTPException(status_code=404, detail="文件已从磁盘移除")
        return FileResponse(
            abs_path,
            filename=att.file_name,
            media_type="application/octet-stream",
        )
    if att.remote_url:
        raise HTTPException(status_code=302, detail="跳转远程 URL", headers={"Location": att.remote_url})
    raise HTTPException(status_code=404, detail="附件无可用文件")
