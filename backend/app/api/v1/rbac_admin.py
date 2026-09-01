"""RBAC 管理 API — 用户/角色/权限 CRUD"""
import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, delete, or_

from app.database import get_db
from app.models.rbac import (
    SysUser, SysRole, SysPermission, SysUserRole, SysRolePermission,
    SysDepartment, SysDataGrant, SysUserPermission,
)
from app.models.project import Project
from app.models.company import Company
from app.models.bid_notice import BidNotice
from app.models.audit import AuditLog
from app.middleware.auth import get_current_user, require_permission
from app.schemas.common import PaginatedResponse
from app.services.cache_service import cache_service
from app.services.data_scope_service import (
    build_data_scope, dept_tree_ids, object_grants, SCOPE_RULES,
)
from app.services.neo4j_sync import sync_user_data_scope

router = APIRouter(prefix="/rbac", tags=["RBAC管理"])

# 对象级授权支持的实体类型与名称解析
_GRANT_ENTITY_MODELS = {
    "project": (Project, Project.name),
    "company": (Company, Company.name),
    "bid": (BidNotice, BidNotice.title),
}


def _grant_entity_name(db: Session, entity_type: str, entity_id: int) -> str:
    """反查授权对象名称, 便于列表展示与审计快照。"""
    spec = _GRANT_ENTITY_MODELS.get(entity_type)
    if not spec:
        return ""
    try:
        row = db.execute(select(spec[1]).where(spec[0].id == entity_id)).scalar_one_or_none()
        return row or ""
    except Exception:  # noqa: BLE001
        return ""


def _user_valid_grants(db: Session, user_id: int):
    """用户未过期的对象级授权记录(按 id 排序)。"""
    now = datetime.datetime.now()
    return list(db.execute(
        select(SysDataGrant).where(
            SysDataGrant.user_id == user_id,
            SysDataGrant.is_deleted == False,  # noqa: E712
            or_(SysDataGrant.expire_at.is_(None), SysDataGrant.expire_at > now),
        ).order_by(SysDataGrant.id)
    ).scalars().all())


def _grant_dicts(rows) -> list[dict]:
    return [{
        "entity_type": r.entity_type, "entity_id": r.entity_id,
        "grant_type": r.grant_type, "expire_at": r.expire_at,
    } for r in rows]


def _sync_user_graph(db: Session, user_id: int) -> None:
    """数据范围/对象授权变更后: 同步 Neo4j 图谱(降级不阻断)。

    注意: 权限缓存失效由调用方(异步 API)显式 await, 避免在同步函数里编排协程。
    """
    su = db.execute(
        select(SysUser).where(SysUser.id == user_id, SysUser.is_deleted == False)  # noqa: E712
    ).scalar_one_or_none()
    try:
        scope = build_data_scope(db, user_id).to_dict() if su else None
        grants = _grant_dicts(_user_valid_grants(db, user_id))
        sync_user_data_scope(user_id, su.person_id if su else None, scope, grants)
    except Exception:  # noqa: BLE001
        pass


def _write_grant_audit(db: Session, user: dict, action: str, target_user_id: int,
                       detail: dict) -> None:
    """授权操作审计: 记录「谁在何时给谁授权/撤销了什么」。"""
    target = db.execute(
        select(SysUser.username, SysUser.display_name).where(SysUser.id == target_user_id)
    ).first()
    db.add(AuditLog(
        user_id=user.get("user_id"), username=user.get("username"),
        action=action, resource_type="user", resource_id=target_user_id,
        resource_name=f"{target[1] or target[0]}" if target else str(target_user_id),
        detail=detail,
    ))
    db.commit()


# ── 用户管理 ──
@router.get("/users", response_model=PaginatedResponse)
async def list_users(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None, is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_rbac")),
):
    stmt = select(SysUser).where(SysUser.is_deleted == False)
    if keyword:
        stmt = stmt.where(SysUser.username.contains(keyword) | SysUser.display_name.contains(keyword))
    if is_active is not None:
        stmt = stmt.where(SysUser.is_active == is_active)
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
    role.data_scope_rule = _valid_scope_rule(body.get("data_scope_rule"))
    role.scope_dept_ids = _valid_dept_ids(body.get("scope_dept_ids"))
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
    if "data_scope_rule" in body:
        role.data_scope_rule = _valid_scope_rule(body.get("data_scope_rule"))
    if "scope_dept_ids" in body:
        role.scope_dept_ids = _valid_dept_ids(body.get("scope_dept_ids"))
    db.commit()
    # 角色数据范围变更 → 影响所有使用该角色的用户
    for uid in db.execute(select(SysUserRole.user_id).where(SysUserRole.role_id == role_id)).scalars().all():
        _sync_user_graph(db, uid)
        await cache_service.invalidate_user_permissions(uid)
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


# ── 部门管理 ──
@router.get("/departments")
async def list_departments(db: Session = Depends(get_db), user: dict = Depends(require_permission("api_rbac"))):
    """部门列表(树形平铺)"""
    rows = db.execute(
        select(SysDepartment).where(SysDepartment.is_deleted == False).order_by(SysDepartment.sort_order)
    ).scalars().all()
    return {"success": True, "data": [
        {"id": d.id, "code": d.code, "name": d.name, "parent_id": d.parent_id, "path": d.path} for d in rows
    ]}


# ── 用户详情/更新/改密/启禁用/删除 ──
def _get_user_or_404(db: Session, user_id: int) -> SysUser:
    row = db.execute(
        select(SysUser).where(SysUser.id == user_id, SysUser.is_deleted == False)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    return row


def _role_ids_of_user(db: Session, user_id: int) -> list[int]:
    return db.execute(
        select(SysUserRole.role_id).where(SysUserRole.user_id == user_id)
    ).scalars().all()


def _admin_user_count(db: Session) -> int:
    admin_role_id = db.execute(
        select(SysRole.id).where(SysRole.code == "admin", SysRole.is_deleted == False)
    ).scalar_one_or_none()
    if not admin_role_id:
        return 0
    return db.execute(
        select(func.count()).select_from(SysUserRole).where(SysUserRole.role_id == admin_role_id)
    ).scalar() or 0


@router.get("/users/{user_id}")
async def get_user_detail(user_id: int, db: Session = Depends(get_db),
                          user: dict = Depends(require_permission("api_rbac"))):
    """用户详情(含角色与部门)"""
    u = _get_user_or_404(db, user_id)
    role_ids = _role_ids_of_user(db, user_id)
    role_codes = db.execute(
        select(SysRole.code).where(SysRole.id.in_(role_ids), SysRole.is_deleted == False)
    ).scalars().all() if role_ids else []
    dept = None
    if u.department_id:
        dept = db.execute(
            select(SysDepartment.name).where(SysDepartment.id == u.department_id, SysDepartment.is_deleted == False)
        ).scalar_one_or_none()
    return {
        "id": u.id, "username": u.username, "display_name": u.display_name,
        "email": u.email, "phone": u.phone, "department_id": u.department_id,
        "department_name": dept, "person_id": u.person_id, "is_active": u.is_active,
        "role_ids": role_ids, "roles": list(role_codes),
        "created_at": u.created_at.isoformat(),
    }


@router.put("/users/{user_id}")
async def update_user(user_id: int, body: dict, db: Session = Depends(get_db),
                      user: dict = Depends(require_permission("api_rbac"))):
    """更新用户资料(显示名/邮箱/手机号/部门)"""
    u = _get_user_or_404(db, user_id)
    if body.get("display_name") is not None:
        u.display_name = str(body["display_name"]).strip() or u.username
    if body.get("email") is not None:
        u.email = body["email"] or None
    if body.get("phone") is not None:
        u.phone = body["phone"] or None
    if "department_id" in body:
        u.department_id = body["department_id"] or None
    db.commit()
    await cache_service.invalidate_user_permissions(user_id)
    return {"success": True, "message": "ok"}


@router.put("/users/{user_id}/password")
async def reset_user_password(user_id: int, body: dict, db: Session = Depends(get_db),
                              user: dict = Depends(require_permission("api_rbac"))):
    """管理员重置用户密码"""
    import re as _re
    from app.services.auth_service import hash_password
    u = _get_user_or_404(db, user_id)
    new_pwd = body.get("new_password", "")
    if not _re.match(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9@#$%^&+=!_\-.*~]{8,64}$", new_pwd):
        raise HTTPException(status_code=400, detail="密码强度不足: 8-64位且须同时包含字母和数字")
    u.password_hash = hash_password(new_pwd)
    db.commit()
    await cache_service.invalidate_user_permissions(user_id)
    return {"success": True, "message": "密码已重置"}


@router.put("/users/{user_id}/active")
async def set_user_active(user_id: int, body: dict, db: Session = Depends(get_db),
                          user: dict = Depends(require_permission("api_rbac"))):
    """启用/禁用用户"""
    u = _get_user_or_404(db, user_id)
    active = bool(body.get("is_active", True))
    # 防呆: 不能禁用自己
    if user_id == user["user_id"] and not active:
        raise HTTPException(status_code=400, detail="不能禁用当前登录账号")
    # 防呆: 不能禁用最后一个管理员
    if not active and u.username == "admin":
        admin_cnt = _admin_user_count(db)
        if admin_cnt <= 1:
            raise HTTPException(status_code=400, detail="不能禁用最后一个管理员账号")
    u.is_active = active
    db.commit()
    await cache_service.invalidate_user_permissions(user_id)
    return {"success": True, "message": "已启用" if active else "已禁用"}


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db),
                      user: dict = Depends(require_permission("api_rbac"))):
    """删除用户(软删, 解除角色关联, 防呆校验)"""
    u = _get_user_or_404(db, user_id)
    if user_id == user["user_id"]:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")
    if u.username == "admin":
        admin_cnt = _admin_user_count(db)
        if admin_cnt <= 1:
            raise HTTPException(status_code=400, detail="不能删除最后一个管理员账号")
    # 解除角色关联
    db.execute(delete(SysUserRole).where(SysUserRole.user_id == user_id))
    u.is_deleted = True
    db.commit()
    await cache_service.invalidate_user_permissions(user_id)
    return {"success": True, "message": "用户已删除"}


# ── 角色权限回显 ──
@router.get("/roles/{role_id}/permissions")
async def get_role_permissions(role_id: int, db: Session = Depends(get_db),
                               user: dict = Depends(require_permission("api_rbac"))):
    """角色已有权限ID列表(用于权限树回显)"""
    role = db.execute(
        select(SysRole).where(SysRole.id == role_id, SysRole.is_deleted == False)
    ).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    ids = db.execute(
        select(SysRolePermission.permission_id).where(SysRolePermission.role_id == role_id)
    ).scalars().all()
    return {"success": True, "data": list(ids)}


# ── 数据范围(分发权限的数据维度) ──
def _valid_scope_rule(rule) -> Optional[str]:
    """校验数据范围规则值, 非法返回 None。"""
    if not rule:
        return None
    rule = str(rule).strip().upper()
    return rule if rule in SCOPE_RULES else None


def _valid_dept_ids(dept_ids) -> Optional[list]:
    """规范化部门ID列表(去重/过滤非数字)。"""
    if dept_ids is None:
        return None
    out = []
    for d in dept_ids or []:
        try:
            v = int(d)
        except (TypeError, ValueError):
            continue
        if v not in out:
            out.append(v)
    return out or None


@router.get("/users/{user_id}/data-scope")
async def get_user_data_scope(user_id: int, db: Session = Depends(get_db),
                              user: dict = Depends(require_permission("api_rbac"))):
    """查看用户数据范围配置(用户级 + 角色继承汇总)。"""
    su = db.execute(
        select(SysUser).where(SysUser.id == user_id, SysUser.is_deleted == False)  # noqa: E712
    ).scalar_one_or_none()
    if not su:
        raise HTTPException(status_code=404, detail="用户不存在")
    scope = build_data_scope(db, user_id)
    return {
        "success": True,
        "data": {
            "user_rule": (su.data_scope_rule or "").upper() or None,
            "user_dept_ids": su.scope_dept_ids or [],
            "effective": scope.to_dict(),
            "roles": [
                {"id": r.id, "code": r.code, "name": r.name,
                 "data_scope_rule": (r.data_scope_rule or "").upper() or None}
                for r in db.execute(
                    select(SysRole).join(SysUserRole, SysUserRole.role_id == SysRole.id)
                    .where(SysUserRole.user_id == user_id, SysRole.is_deleted == False)  # noqa: E712
                ).scalars().all()
            ],
        },
    }


@router.put("/users/{user_id}/data-scope")
async def set_user_data_scope(user_id: int, body: dict, db: Session = Depends(get_db),
                              user: dict = Depends(require_permission("api_rbac"))):
    """设置用户级数据范围(rule + 部门ID列表); rule 为空/NULL 表示恢复继承角色。"""
    su = db.execute(
        select(SysUser).where(SysUser.id == user_id, SysUser.is_deleted == False)  # noqa: E712
    ).scalar_one_or_none()
    if not su:
        raise HTTPException(status_code=404, detail="用户不存在")
    rule = _valid_scope_rule(body.get("rule"))
    su.data_scope_rule = rule
    su.scope_dept_ids = _valid_dept_ids(body.get("dept_ids")) if rule else None
    db.commit()
    _sync_user_graph(db, user_id)
    await cache_service.invalidate_user_permissions(user_id)
    _write_grant_audit(db, user, "data_scope_set", user_id,
                       {"rule": rule, "dept_ids": su.scope_dept_ids})
    return {"success": True, "message": "数据范围已更新"}


@router.get("/users/{user_id}/grants")
async def list_user_grants(user_id: int, db: Session = Depends(get_db),
                           user: dict = Depends(require_permission("api_rbac"))):
    """用户对象级授权列表(含实体名称快照)。"""
    rows = _user_valid_grants(db, user_id)
    return {"success": True, "data": [{
        "id": r.id, "entity_type": r.entity_type, "entity_id": r.entity_id,
        "entity_name": _grant_entity_name(db, r.entity_type, r.entity_id),
        "grant_type": r.grant_type,
        "expire_at": r.expire_at.isoformat() if r.expire_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]}


@router.post("/users/{user_id}/grants")
async def add_user_grants(user_id: int, body: dict, db: Session = Depends(get_db),
                          user: dict = Depends(require_permission("api_rbac"))):
    """批量添加对象级授权。

    body: {"items": [{"entity_type":"project|company|bid", "entity_id":1,
                      "grant_type":"view|own", "expire_at":"2026-12-31"}]}
    """
    su = db.execute(
        select(SysUser).where(SysUser.id == user_id, SysUser.is_deleted == False)  # noqa: E712
    ).scalar_one_or_none()
    if not su:
        raise HTTPException(status_code=404, detail="用户不存在")
    items = body.get("items") or []
    if not items:
        raise HTTPException(status_code=400, detail="items 不能为空")
    if len(items) > 200:
        raise HTTPException(status_code=400, detail="单次最多授权 200 个对象")

    expire_at = None
    if body.get("expire_at"):
        try:
            expire_at = datetime.datetime.fromisoformat(str(body["expire_at"]))
        except ValueError:
            raise HTTPException(status_code=400, detail="expire_at 格式错误, 应为 ISO 日期时间")

    added = 0
    for it in items:
        et = str(it.get("entity_type") or "").strip()
        if et not in _GRANT_ENTITY_MODELS:
            raise HTTPException(status_code=400, detail=f"不支持的实体类型: {et}")
        try:
            eid = int(it.get("entity_id"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="entity_id 必须为整数")
        gt = "own" if str(it.get("grant_type") or "view") == "own" else "view"
        it_expire = expire_at
        if it.get("expire_at") and not body.get("expire_at"):
            try:
                it_expire = datetime.datetime.fromisoformat(str(it["expire_at"]))
            except ValueError:
                raise HTTPException(status_code=400, detail="expire_at 格式错误")
        # 幂等 upsert: 已存在同组合则更新 expire_at/grant_type
        existing = db.execute(select(SysDataGrant).where(
            SysDataGrant.user_id == user_id,
            SysDataGrant.entity_type == et,
            SysDataGrant.entity_id == eid,
            SysDataGrant.grant_type == gt,
            SysDataGrant.is_deleted == False,  # noqa: E712
        )).scalar_one_or_none()
        if existing:
            existing.expire_at = it_expire
            existing.granted_by = user.get("user_id")
        else:
            db.add(SysDataGrant(user_id=user_id, entity_type=et, entity_id=eid,
                                grant_type=gt, expire_at=it_expire,
                                granted_by=user.get("user_id")))
        added += 1
    db.commit()
    _sync_user_graph(db, user_id)
    await cache_service.invalidate_user_permissions(user_id)
    _write_grant_audit(db, user, "grant_add", user_id,
                       {"items": [{"entity_type": i.get("entity_type"), "entity_id": i.get("entity_id"),
                                   "grant_type": i.get("grant_type")} for i in items], "added": added})
    return {"success": True, "added": added, "message": f"已授权 {added} 个对象"}


@router.delete("/users/{user_id}/grants/{grant_id}")
async def remove_user_grant(user_id: int, grant_id: int, db: Session = Depends(get_db),
                            user: dict = Depends(require_permission("api_rbac"))):
    """撤销一条对象级授权。"""
    row = db.execute(select(SysDataGrant).where(
        SysDataGrant.id == grant_id,
        SysDataGrant.user_id == user_id,
        SysDataGrant.is_deleted == False,  # noqa: E712
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="授权记录不存在")
    row.is_deleted = True
    db.commit()
    _sync_user_graph(db, user_id)
    await cache_service.invalidate_user_permissions(user_id)
    _write_grant_audit(db, user, "grant_revoke", user_id,
                       {"entity_type": row.entity_type, "entity_id": row.entity_id,
                        "grant_type": row.grant_type})
    return {"success": True, "message": "已撤销授权"}


# ── 用户级功能直授(绕过角色, 例外/临时授权) ──
@router.get("/users/{user_id}/permissions")
async def list_user_direct_permissions(user_id: int, db: Session = Depends(get_db),
                                       user: dict = Depends(require_permission("api_rbac"))):
    """用户直授权限ID列表(用于权限树回显)。"""
    su = db.execute(
        select(SysUser).where(SysUser.id == user_id, SysUser.is_deleted == False)  # noqa: E712
    ).scalar_one_or_none()
    if not su:
        raise HTTPException(status_code=404, detail="用户不存在")
    ids = db.execute(
        select(SysUserPermission.permission_id).where(
            SysUserPermission.user_id == user_id,
            SysUserPermission.is_deleted == False,  # noqa: E712
        )
    ).scalars().all()
    return {"success": True, "data": list(ids)}


@router.put("/users/{user_id}/permissions")
async def set_user_direct_permissions(user_id: int, body: dict,
                                      db: Session = Depends(get_db),
                                      user: dict = Depends(require_permission("api_rbac"))):
    """全量替换用户直授权限(与角色权限取并集生效)。"""
    su = db.execute(
        select(SysUser).where(SysUser.id == user_id, SysUser.is_deleted == False)  # noqa: E712
    ).scalar_one_or_none()
    if not su:
        raise HTTPException(status_code=404, detail="用户不存在")
    perm_ids = body.get("permission_ids", [])
    # 删除旧直授
    db.execute(delete(SysUserPermission).where(SysUserPermission.user_id == user_id))
    # 写入新直授(过滤合法权限ID)
    if perm_ids:
        valid = db.execute(
            select(SysPermission.id).where(
                SysPermission.id.in_(perm_ids),
                SysPermission.is_deleted == False,  # noqa: E712
            )
        ).scalars().all()
        for pid in valid:
            db.add(SysUserPermission(user_id=user_id, permission_id=pid,
                                     granted_by=user.get("user_id")))
    db.commit()
    await cache_service.invalidate_user_permissions(user_id)
    _write_grant_audit(db, user, "perm_grant", user_id,
                       {"permission_ids": list(perm_ids)})
    return {"success": True, "message": "直授权限已更新"}
