"""选项集管理 API"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.models.option_set import OptionSet, OptionItem
from app.middleware.auth import get_current_user, require_permission
from app.schemas.common import PaginatedResponse
from app.services.cache_service import cache_service

router = APIRouter(prefix="/option-sets", tags=["选项集"])


@router.get("")
async def list_option_sets(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """选项集列表"""
    stmt = select(OptionSet).where(OptionSet.is_deleted == False)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0

    sets = db.execute(
        stmt.offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()

    return PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[{"id": s.id, "code": s.code, "name": s.name, "description": s.description} for s in sets],
    )


@router.get("/{code}/items")
async def get_option_items(
    code: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    获取选项集及其选项项 — 供前端下拉框渲染

    请求示例:
      GET /api/v1/option-sets/project_status/items

    响应示例:
      ```json
      {
        "code": "project_status", "name": "项目状态",
        "items": [
          {"value": "active", "label": "进行中", "color": "#1890ff", "sort_order": 1},
          {"value": "suspended", "label": "挂起", "color": "#faad14", "sort_order": 2}
        ]
      }
      ```
    """
    # 先查缓存
    cached = await cache_service.get_option_set(code)
    if cached:
        return cached

    option_set = db.execute(
        select(OptionSet).where(OptionSet.code == code, OptionSet.is_deleted == False)
    ).scalar_one_or_none()

    if not option_set:
        raise HTTPException(status_code=404, detail="选项集不存在")

    items = db.execute(
        select(OptionItem)
        .where(OptionItem.option_set_id == option_set.id, OptionItem.is_deleted == False)
        .order_by(OptionItem.sort_order)
    ).scalars().all()

    result = {
        "code": option_set.code,
        "name": option_set.name,
        "items": [
            {
                "value": i.value,
                "label": i.label,
                "color": i.color,
                "sort_order": i.sort_order,
            }
            for i in items
        ],
    }

    # 写缓存
    await cache_service.set_option_set(code, result)

    return result


@router.post("/{code}/items", status_code=status.HTTP_201_CREATED)
async def add_option_item(
    code: str,
    item_data: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_option_crud")),
):
    """添加选项项 — 同时失效缓存"""
    option_set = db.execute(
        select(OptionSet).where(OptionSet.code == code, OptionSet.is_deleted == False)
    ).scalar_one_or_none()

    if not option_set:
        raise HTTPException(status_code=404, detail="选项集不存在")

    item = OptionItem(
        option_set_id=option_set.id,
        value=item_data.get("value", ""),
        label=item_data.get("label", ""),
        sort_order=item_data.get("sort_order", 0),
        color=item_data.get("color"),
    )
    db.add(item)
    db.commit()

    # 失效缓存
    await cache_service.invalidate_option_set(code)

    return {"id": item.id, "value": item.value, "label": item.label}


@router.put("/{code}/items/{value}")
async def update_option_item(
    code: str,
    value: str,
    item_data: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_option_crud")),
):
    """更新选项项(label/排序/颜色) — 同时失效缓存"""
    option_set = db.execute(
        select(OptionSet).where(OptionSet.code == code, OptionSet.is_deleted == False)
    ).scalar_one_or_none()
    if not option_set:
        raise HTTPException(status_code=404, detail="选项集不存在")

    item = db.execute(
        select(OptionItem).where(
            OptionItem.option_set_id == option_set.id,
            OptionItem.value == value,
            OptionItem.is_deleted == False,
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="选项项不存在")

    if "label" in item_data:
        item.label = item_data["label"]
    if "sort_order" in item_data:
        item.sort_order = item_data["sort_order"]
    if "color" in item_data:
        item.color = item_data["color"]
    db.commit()

    # 失效缓存
    await cache_service.invalidate_option_set(code)

    return {"id": item.id, "value": item.value, "label": item.label}
