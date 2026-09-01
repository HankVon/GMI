"""前台首页内容配置(CMS) 管理 API — 首页配置中心。

权限:
- 查看: cms_home_view
- 编辑: cms_home_edit(增删改均需该权限)

对应前台: /public/home-config(公开读取, 见 public.py)
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cms import CmsBlock, CmsBlockItem
from app.middleware.auth import get_current_user, require_permission
from app.schemas.cms import (
    CmsBlockCreate, CmsBlockUpdate,
    CmsBlockItemCreate, CmsBlockItemUpdate,
)
from app.schemas.common import PaginatedResponse
from app.services.cms import get_all_blocks, get_block_with_items, serialize_item

router = APIRouter(prefix="/cms", tags=["首页内容配置"])


# ─────────────────────────── 区块管理 ───────────────────────────

@router.get("/blocks")
async def list_cms_blocks(
    page: str = Query("", max_length=32, description="按页面过滤: home/about/contact/solutions/intelligence/datacenter, 空=全部"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("cms_home_view")),
):
    """区块列表(含条目), 可按页面过滤, 供后台配置中心渲染。"""
    return {"success": True, "data": get_all_blocks(db, page or None)}


@router.post("/blocks", status_code=status.HTTP_201_CREATED)
async def create_cms_block(
    payload: CmsBlockCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("cms_home_edit")),
):
    """新建区块(page_key 指定所属前台页面)。"""
    exists = db.execute(
        select(CmsBlock).where(
            CmsBlock.page_key == payload.page_key,
            CmsBlock.block_key == payload.block_key,
            CmsBlock.is_deleted == False,
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail=f"页面 {payload.page_key} 下区块标识 {payload.block_key} 已存在")
    block = CmsBlock(
        page_key=payload.page_key,
        block_key=payload.block_key,
        title=payload.title,
        description=payload.description,
        enabled=payload.enabled,
        sort_order=payload.sort_order,
        extra=payload.extra or {},
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return {"success": True, "data": {"id": block.id, "page_key": block.page_key, "block_key": block.block_key}}


@router.put("/blocks/{page_key}/{block_key}")
async def update_cms_block(
    page_key: str,
    block_key: str,
    payload: CmsBlockUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("cms_home_edit")),
):
    """更新区块(title/描述/启用/排序/扩展配置)。"""
    block = db.execute(
        select(CmsBlock).where(
            CmsBlock.page_key == page_key,
            CmsBlock.block_key == block_key,
            CmsBlock.is_deleted == False,
        )
    ).scalar_one_or_none()
    if not block:
        raise HTTPException(status_code=404, detail="区块不存在")
    if payload.title is not None:
        block.title = payload.title
    if payload.description is not None:
        block.description = payload.description
    if payload.enabled is not None:
        block.enabled = payload.enabled
    if payload.sort_order is not None:
        block.sort_order = payload.sort_order
    if payload.extra is not None:
        block.extra = payload.extra
    db.commit()
    return {"success": True, "data": get_block_with_items(db, block)}


@router.delete("/blocks/{page_key}/{block_key}")
async def delete_cms_block(
    page_key: str,
    block_key: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("cms_home_edit")),
):
    """软删除区块及其全部条目。"""
    block = db.execute(
        select(CmsBlock).where(
            CmsBlock.page_key == page_key,
            CmsBlock.block_key == block_key,
            CmsBlock.is_deleted == False,
        )
    ).scalar_one_or_none()
    if not block:
        raise HTTPException(status_code=404, detail="区块不存在")
    block.is_deleted = True
    items = db.execute(
        select(CmsBlockItem).where(CmsBlockItem.block_id == block.id)
    ).scalars().all()
    for it in items:
        it.is_deleted = True
    db.commit()
    return {"success": True}


# ─────────────────────────── 条目管理 ───────────────────────────

def _get_block(db: Session, page_key: str, block_key: str) -> CmsBlock:
    """按页面+区块标识定位区块, 不存在则 404。"""
    block = db.execute(
        select(CmsBlock).where(
            CmsBlock.page_key == page_key,
            CmsBlock.block_key == block_key,
            CmsBlock.is_deleted == False,
        )
    ).scalar_one_or_none()
    if not block:
        raise HTTPException(status_code=404, detail="区块不存在")
    return block


@router.get("/blocks/{page_key}/{block_key}/items")
async def list_cms_block_items(
    page_key: str,
    block_key: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("cms_home_view")),
):
    """某区块的条目列表。"""
    block = _get_block(db, page_key, block_key)
    items = db.execute(
        select(CmsBlockItem)
        .where(CmsBlockItem.block_id == block.id, CmsBlockItem.is_deleted == False)
        .order_by(CmsBlockItem.sort_order, CmsBlockItem.id)
    ).scalars().all()
    return {"success": True, "data": [serialize_item(i) for i in items]}


@router.post("/blocks/{page_key}/{block_key}/items", status_code=status.HTTP_201_CREATED)
async def create_cms_block_item(
    page_key: str,
    block_key: str,
    payload: CmsBlockItemCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("cms_home_edit")),
):
    """新增区块条目。"""
    block = _get_block(db, page_key, block_key)
    item = CmsBlockItem(
        block_id=block.id,
        item_key=payload.item_key,
        title=payload.title,
        subtitle=payload.subtitle,
        icon=payload.icon,
        link=payload.link,
        meta=payload.meta or {},
        enabled=payload.enabled,
        sort_order=payload.sort_order,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"success": True, "data": serialize_item(item)}


@router.put("/blocks/{page_key}/{block_key}/items/{item_id}")
async def update_cms_block_item(
    page_key: str,
    block_key: str,
    item_id: int,
    payload: CmsBlockItemUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("cms_home_edit")),
):
    """更新区块条目。"""
    block = _get_block(db, page_key, block_key)
    item = db.get(CmsBlockItem, item_id)
    if not item or item.is_deleted or item.block_id != block.id:
        raise HTTPException(status_code=404, detail="条目不存在")
    if payload.item_key is not None:
        item.item_key = payload.item_key
    if payload.title is not None:
        item.title = payload.title
    if payload.subtitle is not None:
        item.subtitle = payload.subtitle
    if payload.icon is not None:
        item.icon = payload.icon
    if payload.link is not None:
        item.link = payload.link
    if payload.meta is not None:
        item.meta = payload.meta
    if payload.enabled is not None:
        item.enabled = payload.enabled
    if payload.sort_order is not None:
        item.sort_order = payload.sort_order
    db.commit()
    db.refresh(item)
    return {"success": True, "data": serialize_item(item)}


@router.delete("/blocks/{page_key}/{block_key}/items/{item_id}")
async def delete_cms_block_item(
    page_key: str,
    block_key: str,
    item_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("cms_home_edit")),
):
    """软删除区块条目。"""
    _get_block(db, page_key, block_key)
    item = db.get(CmsBlockItem, item_id)
    if not item or item.is_deleted:
        raise HTTPException(status_code=404, detail="条目不存在")
    item.is_deleted = True
    db.commit()
    return {"success": True}
