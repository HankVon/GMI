"""RBAC 管理 API — 用户/角色/权限 CRUD"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, delete

from app.database import get_db
from app.models.rbac import SysUser, SysRole, SysPermission, SysUserRole, SysRolePermission
from app.middleware.auth import get_current_user, require_permission
from app.schemas.common import PaginatedResponse
from app.services.cache_service import cache_service

router = APIRouter(prefix="/rbac", tags=["RBAC管理"])


# ── 用户管理 ──
@router.get("/users", response_model=PaginatedResponse)
async def list_users(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None, db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_rbac")),
):
    stmt = select(SysUser).where(SysUser.is_deleted == False)
    if keyword:
        stmt = stmt.where(SysUser.username.contains(keyword))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    items = []
    for u in rows:
        # 加载角色
        roles = db.execute(
            select(SysRole.code).join(SysUserRole, SysRole.id == SysUserRole.role_id)
            .where(SysUserRole.user_id == u.id)
        ).scalars().all()
        items.append({
            "id": u.id, "username": u.username, "display_name": u.display_name,
            "email": u.email, "department_id": u.department_id, "is_active": u.is_active,
            "roles": [r for r in roles], "created_at": u.created_at.isoformat(),
        })
    return PaginatedResponse(total=total, page=page, page_size=page_size, items=items)


@router.put("/users/{user_id}/roles")
async def set_user_roles(user_id: int, body: dict,
                         db: Session = Depends(get_db),
                         user: dict = Depends(require_permission("api_rbac"))):
    """全量替换用户角色，变更后失效该用户权限缓存"""
    role_ids = body.get("role_ids", [])
    # 删除旧关联
    db.execute(delete(SysUserRole).where(SysUserRole.user_id == user_id))
    # 写入新关联
    import datetime
    for rid in role_ids:
        db.add(SysUserRole(user_id=user_id, role_id=rid, created_at=datetime.datetime.now()))
    db.commit()
    # 失效权限缓存
    await cache_service.invalidate_user_permissions(user_id)
    return {"success": True, "message": "ok"}


# ── 角色管理 ──
@router.get("/roles")
async def list_roles(db: Session = Depends(get_db), user: dict = Depends(require_permission("api_rbac"))):
    rows = db.execute(select(SysRole).where(SysRole.is_deleted == False)).scalars().all()
    items = []
    for r in rows:
        user_cnt = db.execute(select(func.count()).select_from(SysUserRole).where(SysUserRole.role_id == r.id)).scalar() or 0
        perm_cnt = db.execute(select(func.count()).select_from(SysRolePermission).where(SysRolePermission.role_id == r.id)).scalar() or 0
        items.append({"id": r.id, "code": r.code, "name": r.name, "description": r.description,
                       "user_count": user_cnt, "permission_count": perm_cnt})
    return {"success": True, "data": items}


@router.post("/roles", status_code=status.HTTP_201_CREATED)
async def create_role(body: dict, db: Session = Depends(get_db), user: dict = Depends(require_permission("api_rbac"))):
    existing = db.execute(select(SysRole).where(SysRole.code == body.get("code"), SysRole.is_deleted == False)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="role code exists")
    role = SysRole(code=body["code"], name=body["name"], description=body.get("description"))
    db.add(role); db.commit(); db.refresh(role)
    return {"success": True, "data": {"id": role.id, "code": role.code}}


@router.put("/roles/{role_id}")
async def update_role(role_id: int, body: dict, db: Session = Depends(get_db), user: dict = Depends(require_permission("api_rbac"))):
    role = db.execute(select(SysRole).where(SysRole.id == role_id, SysRole.is_deleted == False)).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="role not found")
    if role.code == "admin" and body.get("code") and body["code"] != "admin":
        raise HTTPException(status_code=403, detail="cannot change admin code")
    if body.get("code"):
        role.code = body["code"]
    if body.get("name"):
        role.name = body["name"]
    if "description" in body:
        role.description = body["description"]
    db.commit()
    return {"success": True, "message": "ok"}


@router.delete("/roles/{role_id}")
async def delete_role(role_id: int, db: Session = Depends(get_db), user: dict = Depends(require_permission("api_rbac"))):
    role = db.execute(select(SysRole).where(SysRole.id == role_id, SysRole.is_deleted == False)).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="role not found")
    if role.code == "admin":
        raise HTTPException(status_code=403, detail="cannot delete admin role")
    user_cnt = db.execute(select(func.count()).select_from(SysUserRole).where(SysUserRole.role_id == role_id)).scalar() or 0
    if user_cnt > 0:
        raise HTTPException(status_code=409, detail=f"role has {user_cnt} users, unassign first")
    role.is_deleted = True; db.commit()
    return None


# ── 权限管理 ──
@router.get("/permissions")
async def list_permissions(db: Session = Depends(get_db), user: dict = Depends(require_permission("api_rbac"))):
    rows = db.execute(select(SysPermission).where(SysPermission.is_deleted == False)).scalars().all()
    items = [{"id": r.id, "code": r.code, "name": r.name, "resource_type": r.resource_type,
              "resource_value": r.resource_value, "parent_id": r.parent_id, "sort_order": r.sort_order} for r in rows]
    return {"success": True, "data": items}


@router.put("/roles/{role_id}/permissions")
async def set_role_permissions(role_id: int, body: dict,
                                db: Session = Depends(get_db),
                                user: dict = Depends(require_permission("api_rbac"))):
    """全量替换角色权限，变更后失效所有该角色用户的权限缓存"""
    perm_ids = body.get("permission_ids", [])
    db.execute(delete(SysRolePermission).where(SysRolePermission.role_id == role_id))
    import datetime
    for pid in perm_ids:
        db.add(SysRolePermission(role_id=role_id, permission_id=pid, created_at=datetime.datetime.now()))
    db.commit()
    # 失效所有使用该角色的用户缓存
    user_rows = db.execute(select(SysUserRole.user_id).where(SysUserRole.role_id == role_id)).scalars().all()
    for uid in user_rows:
        await cache_service.invalidate_user_permissions(uid)
    return {"success": True, "message": "ok"}
