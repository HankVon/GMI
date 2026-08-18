"""
★ 动态实体 CRUD API ★
通用路由：按元数据驱动的实体CURD（校验流程完整）
用于后续扩展新业务实体时无需新增API路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, text

from app.database import get_db
from app.models.field_meta import FieldMetadata
from app.models.project import Project
from app.models.person import Person
from app.models.project_member import ProjectMember
from app.models.company import Company
from app.models.rbac import SysDepartment
from app.models.option_set import OptionSet, OptionItem
from app.middleware.auth import get_current_user, require_permission
from app.schemas.common import APIResponse
from app.services.dynamic_field_engine import (
    validate_ext_attrs,
    filter_fields_by_permission,
)
from app.services.cache_service import cache_service
from app.services.audit_service import log_action, track_field_changes, compute_ext_attr_changes

router = APIRouter(prefix="/dynamic", tags=["动态CRUD"])

# 实体表映射
ENTITY_TABLE_MAP = {
    "project": Project,
    "person": Person,
    "project_member": ProjectMember,
    "company": Company,
    "department": SysDepartment,
}


@router.get("/{entity_type}/form-config")
async def get_form_config(
    entity_type: str,
    mode: str = Query("edit", description="view/edit"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    获取实体的动态表单配置 — 供前端渲染表单

    请求示例:
      GET /api/v1/dynamic/project/form-config?mode=edit

    响应示例:
      ```json
      {
        "entity_type": "project",
        "fields": [
          {
            "field_key": "contract_amount", "display_name": "合同金额",
            "data_type": "money", "is_required": false,
            "validation_rules": {"min": 0},
            "sort_order": 1, "group_name": "合同信息",
            "placeholder": "请输入金额",
            "options": null
          }
        ]
      }
      ```
    """
    if entity_type not in ENTITY_TABLE_MAP:
        raise HTTPException(status_code=400, detail=f"不支持的实体类型: {entity_type}")

    user_roles = user.get("roles", [])

    # 从缓存获取字段元数据
    cached = await cache_service.get_field_meta_list(entity_type)
    if cached:
        meta_list = cached
    else:
        meta_objs = db.execute(
            select(FieldMetadata).where(
                FieldMetadata.entity_type == entity_type,
                FieldMetadata.status == "enabled",
                FieldMetadata.is_deleted == False,
            ).order_by(FieldMetadata.sort_order)
        ).scalars().all()
        meta_list = [
            {
                "field_key": m.field_key, "display_name": m.display_name,
                "data_type": m.data_type, "option_set_code": m.option_set_code,
                "validation_rules": m.validation_rules, "sort_order": m.sort_order,
                "group_name": m.group_name, "is_required": m.is_required,
                "is_list_visible": m.is_list_visible,
                "placeholder": m.placeholder, "help_text": m.help_text,
                "field_permissions": m.field_permissions, "default_value": m.default_value,
            }
            for m in meta_objs
        ]
        await cache_service.set_field_meta_list(entity_type, meta_list)

    # 字段级权限过滤
    filtered_fields = []
    for meta in meta_list:
        perms = meta.get("field_permissions") or {}
        allowed_roles = perms.get(mode, [])
        if not allowed_roles or any(r in allowed_roles for r in user_roles):
            # 附加选项
            field_data = dict(meta)
            if meta.get("data_type") == "entity_ref" and meta.get("option_set_code") in ENTITY_TABLE_MAP:
                # 关联实体：拉取 id/name 选项
                ref_entity = ENTITY_TABLE_MAP[meta["option_set_code"]]
                rows = db.execute(
                    select(ref_entity.id, ref_entity.name)
                    .where(ref_entity.is_deleted == False)
                    .order_by(ref_entity.id)
                    .limit(300)
                ).all()
                field_data["options"] = [{"value": r[0], "label": r[1]} for r in rows]
            elif meta.get("option_set_code"):
                code = meta["option_set_code"]
                opts = await cache_service.get_option_set(code)
                if not opts:
                    # 缓存 miss 时回源数据库, 避免 form-config 返回空选项导致详情页显示原始值
                    option_set = db.execute(
                        select(OptionSet).where(OptionSet.code == code, OptionSet.is_deleted == False)
                    ).scalar_one_or_none()
                    if option_set:
                        items = db.execute(
                            select(OptionItem)
                            .where(OptionItem.option_set_id == option_set.id, OptionItem.is_deleted == False)
                            .order_by(OptionItem.sort_order)
                        ).scalars().all()
                        opts = {
                            "code": code,
                            "name": option_set.name,
                            "items": [
                                {"value": i.value, "label": i.label, "color": i.color, "sort_order": i.sort_order}
                                for i in items
                            ],
                        }
                        await cache_service.set_option_set(code, opts)
                field_data["options"] = opts["items"] if opts else []
            else:
                field_data["options"] = None
            filtered_fields.append(field_data)

    return {
        "entity_type": entity_type,
        "fields": filtered_fields,
    }


@router.get("/{entity_type}/{entity_id}/validate")
async def validate_entity_fields(
    entity_type: str,
    entity_id: int,
    ext_attrs: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    校验实体的动态字段（前端即时校验调此接口）

    请求示例:
      POST /api/v1/dynamic/project/1/validate
      {"ext_attrs": {"contract_amount": "not-a-number"}}

    响应示例:
      ```json
      {"success": false, "message": "contract_amount: Input should be a valid decimal"}
      ```
    """
    if entity_type not in ENTITY_TABLE_MAP:
        raise HTTPException(status_code=400, detail="不支持的实体类型")

    meta_objs = db.execute(
        select(FieldMetadata).where(
            FieldMetadata.entity_type == entity_type,
            FieldMetadata.status == "enabled",
            FieldMetadata.is_deleted == False,
        )
    ).scalars().all()

    ok, cleaned, err = validate_ext_attrs(entity_type, ext_attrs, meta_objs)

    return APIResponse(success=ok, message=err or "校验通过", data={"cleaned": cleaned} if ok else None)
