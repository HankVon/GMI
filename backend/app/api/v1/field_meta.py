"""字段元数据管理 API — 动态字段引擎中枢"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.models.field_meta import FieldMetadata, FieldMetadataVersion
from app.middleware.auth import get_current_user, require_permission
from app.schemas.field_meta import FieldMetadataCreate, FieldMetadataUpdate, FieldMetadataResponse
from app.schemas.common import PaginatedResponse
from app.services.cache_service import cache_service
from app.services.dynamic_query import generate_virtual_column_ddl
import logging

logger = logging.getLogger("field_meta")

router = APIRouter(prefix="/field-metadata", tags=["字段元数据"])


async def _invalidate_cache_background(entity_type: str):
    """后台任务：失效缓存(直接 await,确保在响应后立即执行)"""
    await cache_service.invalidate_field_meta(entity_type)


@router.get("", response_model=PaginatedResponse)
async def list_field_metadata(
    entity_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    字段元数据列表

    请求示例:
      GET /api/v1/field-metadata?entity_type=project&status=enabled
    """
    stmt = select(FieldMetadata).where(FieldMetadata.is_deleted == False)

    if entity_type:
        stmt = stmt.where(FieldMetadata.entity_type == entity_type)
    if status:
        stmt = stmt.where(FieldMetadata.status == status)

    stmt = stmt.order_by(FieldMetadata.sort_order.asc(), FieldMetadata.created_at.asc())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    metas = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()

    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[FieldMetadataResponse.model_validate(m) for m in metas],
    )


@router.post("", response_model=FieldMetadataResponse, status_code=status.HTTP_201_CREATED)
async def create_field_metadata(
    data: FieldMetadataCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_field_crud")),
):
    """
    新增动态字段

    请求示例:
      ```json
      {
        "entity_type": "project",
        "field_key": "contract_amount",
        "display_name": "合同金额",
        "data_type": "money",
        "is_list_visible": true,
        "is_searchable": true,
        "is_filterable": true,
        "is_exportable": true,
        "field_permissions": {"view": ["admin","project_mgr"], "edit": ["admin"]},
        "validation_rules": {"min": 0, "max": 999999999},
        "group_name": "合同信息"
      }
      ```

    后端行为:
      1. 写入 field_metadata 表
      2. 写入 field_metadata_version 版本
      3. 失效 Redis 中该实体类型缓存
      4. (可选)为 MySQL 建虚拟列 + 索引
    """
    existing = db.execute(
        select(FieldMetadata).where(
            FieldMetadata.entity_type == data.entity_type,
            FieldMetadata.field_key == data.field_key,
            FieldMetadata.is_deleted == False,
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"实体 '{data.entity_type}' 下字段 '{data.field_key}' 已存在",
        )

    meta = FieldMetadata(**data.model_dump(exclude_none=True))
    db.add(meta)
    db.flush()

    # 版本快照
    version = FieldMetadataVersion(
        field_meta_id=meta.id,
        version=1,
        snapshot=data.model_dump(exclude_none=True),
        change_type="create",
        changed_by=user.get("user_id"),
        changed_at=func.now(),
    )
    db.add(version)
    db.commit()
    db.refresh(meta)

    # 失效缓存
    background_tasks.add_task(_invalidate_cache_background, data.entity_type)
    # 异步建虚拟列
    background_tasks.add_task(_sync_virtual_column, meta)

    return FieldMetadataResponse.model_validate(meta)


@router.post("/sync-indexes")
async def sync_all_indexes(
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_field_crud")),
):
    """admin 兜底：扫描所有 is_filterable/is_searchable=true 字段，补齐缺失虚拟列(幂等)"""
    metas = db.execute(
        select(FieldMetadata).where(FieldMetadata.is_deleted == False, FieldMetadata.status == "enabled")
    ).scalars().all()
    created, skipped = [], []
    for m in metas:
        if not (m.is_searchable or m.is_filterable):
            skipped.append(m.field_key); continue
        ddl = generate_virtual_column_ddl(m)
        if not ddl:
            skipped.append(m.field_key); continue
        try:
            for stmt in ddl.split(";"):
                s = stmt.strip()
                if s:
                    db.execute(text(s))
            db.commit()
            created.append(m.field_key)
        except Exception as e:
            db.rollback()
            if "Duplicate column" in str(e):
                skipped.append(m.field_key)
            else:
                logger.warning("[sync-index] skip %s.%s: %s", m.entity_type, m.field_key, e)
                skipped.append(m.field_key)
    return {"success": True, "data": {"created": created, "skipped": skipped}}


async def _sync_virtual_column(meta: FieldMetadata):
    """后台任务：为 is_filterable/is_searchable 字段建虚拟列+索引"""
    ddl = generate_virtual_column_ddl(meta)
    if not ddl:
        return
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            for stmt in ddl.split(";"):
                stmt = stmt.strip()
                if stmt:
                    db.execute(text(stmt))
            db.commit()
            logger.info("[virtual_column] created for %s.%s", meta.entity_type, meta.field_key)
        except Exception as e:
            db.rollback()
            logger.warning("[virtual_column] failed for %s.%s: %s", meta.entity_type, meta.field_key, e)
        finally:
            db.close()
    except Exception as e:
        logger.warning("[virtual_column] session error: %s", e)


@router.put("/{field_id}", response_model=FieldMetadataResponse)
async def update_field_metadata(
    field_id: int,
    data: FieldMetadataUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_field_crud")),
):
    """
    更新字段元数据（字段标识不可改）

    请求示例:
      ```json
      {
        "display_name": "合同总额",
        "is_list_visible": false,
        "validation_rules": {"min": 100000, "max": 999999999}
      }
      ```
    """
    meta = db.execute(
        select(FieldMetadata).where(
            FieldMetadata.id == field_id,
            FieldMetadata.is_deleted == False,
        )
    ).scalar_one_or_none()

    if not meta:
        raise HTTPException(status_code=404, detail="字段元数据不存在")

    update_data = data.model_dump(exclude_none=True)

    # 软更新标记
    for key, val in update_data.items():
        setattr(meta, key, val)

    # 版本快照
    current_version = db.execute(
        select(func.max(FieldMetadataVersion.version)).where(
            FieldMetadataVersion.field_meta_id == field_id
        )
    ).scalar() or 0

    version = FieldMetadataVersion(
        field_meta_id=field_id,
        version=current_version + 1,
        snapshot=update_data,
        change_type="update",
        changed_by=user.get("user_id"),
        changed_at=func.now(),
    )
    db.add(version)
    db.commit()
    db.refresh(meta)

    # 失效缓存
    background_tasks.add_task(_invalidate_cache_background, meta.entity_type)

    return FieldMetadataResponse.model_validate(meta)


@router.delete("/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_field_metadata(
    field_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_field_crud")),
):
    """软删除字段元数据 — 历史数据保留在 ext_attrs 中"""
    meta = db.execute(
        select(FieldMetadata).where(
            FieldMetadata.id == field_id,
            FieldMetadata.is_deleted == False,
        )
    ).scalar_one_or_none()

    if not meta:
        raise HTTPException(status_code=404, detail="字段元数据不存在")

    # 检查是否为受保护的系统字段
    SYSTEM_FIELDS = {"code", "name", "description", "status", "manager_id",
                     "start_date", "end_date", "department_id"}
    if meta.field_key in SYSTEM_FIELDS and meta.entity_type == "project":
        raise HTTPException(
            status_code=403,
            detail=f"系统字段 '{meta.field_key}' 受保护不可删除",
        )

    entity_type = meta.entity_type

    meta.is_deleted = True

    # 版本记录
    current_version = db.execute(
        select(func.max(FieldMetadataVersion.version)).where(
            FieldMetadataVersion.field_meta_id == field_id
        )
    ).scalar() or 0

    version = FieldMetadataVersion(
        field_meta_id=field_id,
        version=current_version + 1,
        snapshot=FieldMetadataResponse.model_validate(meta).model_dump(mode="json"),
        change_type="delete",
        changed_by=user.get("user_id"),
        changed_at=func.now(),
    )
    db.add(version)
    db.commit()

    background_tasks.add_task(_invalidate_cache_background, entity_type)
    return None
