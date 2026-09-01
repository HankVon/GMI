"""前台页面内容配置(CMS) 服务 — 序列化与公开配置组装。

职责:
- 管理端: 区块/条目 CRUD 的数据序列化(统一字段契约), 支持按页面(page_key)过滤。
- 公开端: 组装 /public/home-config 返回的页面配置(仅 enabled 区块+条目)。

页面维度: CmsBlock.page_key 区分所属前台页面(home/about/contact/solutions/
intelligence/datacenter), 后台按页面管理, 前台按页面拉取。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cms import CmsBlock, CmsBlockItem


def serialize_item(item: CmsBlockItem) -> dict:
    """条目序列化为前台字段契约。"""
    meta = item.meta if isinstance(item.meta, dict) else {}
    return {
        "id": item.id,
        "item_key": item.item_key,
        "title": item.title,
        "subtitle": item.subtitle,
        "icon": item.icon,
        "link": item.link,
        "meta": meta,
        "enabled": item.enabled,
        "sort_order": item.sort_order,
    }


def serialize_block(block: CmsBlock, items: list[CmsBlockItem]) -> dict:
    """区块序列化(含条目列表, 按 sort_order 排序)。"""
    extra = block.extra if isinstance(block.extra, dict) else {}
    return {
        "id": block.id,
        "page_key": block.page_key,
        "block_key": block.block_key,
        "title": block.title,
        "description": block.description,
        "enabled": block.enabled,
        "sort_order": block.sort_order,
        "extra": extra,
        "items": [serialize_item(i) for i in items],
    }


def get_block_with_items(db: Session, block: CmsBlock) -> dict:
    """查询区块及其启用条目并序列化。"""
    items = db.execute(
        select(CmsBlockItem)
        .where(CmsBlockItem.block_id == block.id, CmsBlockItem.is_deleted == False)
        .order_by(CmsBlockItem.sort_order, CmsBlockItem.id)
    ).scalars().all()
    return serialize_block(block, items)


def get_all_blocks(db: Session, page: str | None = None) -> list[dict]:
    """管理端: 全部区块(含条目), 可按页面过滤, 按排序返回。"""
    stmt = select(CmsBlock).where(CmsBlock.is_deleted == False)
    if page:
        stmt = stmt.where(CmsBlock.page_key == page)
    blocks = db.execute(stmt.order_by(CmsBlock.sort_order, CmsBlock.id)).scalars().all()
    return [get_block_with_items(db, b) for b in blocks]


def get_public_config(db: Session, page: str = "home") -> dict:
    """公开端: 仅返回指定页面启用的区块及其启用条目。

    返回结构按 block_key 组织, 便于前台按区块取用:
    {
      "page": "home",
      "blocks": {"top_guide": {...}, ...},
      "order": ["top_guide", ...]
    }
    """
    blocks = db.execute(
        select(CmsBlock).where(
            CmsBlock.is_deleted == False,
            CmsBlock.enabled == 1,
            CmsBlock.page_key == page,
        ).order_by(CmsBlock.sort_order, CmsBlock.id)
    ).scalars().all()
    result: dict = {}
    order: list[str] = []
    for b in blocks:
        block_data = get_block_with_items(db, b)
        block_data["items"] = [it for it in block_data["items"] if it["enabled"]]
        result[b.block_key] = block_data
        order.append(b.block_key)
    return {"page": page, "blocks": result, "order": order}
