"""
认证服务: JWT签发+验证+密码哈希
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.config import settings
from app.models.rbac import (
    SysUser, SysUserRole, SysRole, SysRolePermission, SysPermission, SysUserPermission,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── 密码工具 ──
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT工具 ──
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


# ── 权限查询 ──
def get_user_with_permissions(db: Session, user_id: int) -> Optional[dict]:
    """根据用户ID获取角色和权限列表(不带缓存)"""
    user = db.execute(
        select(SysUser).where(SysUser.id == user_id, SysUser.is_deleted == False)
    ).scalar_one_or_none()

    if not user or not user.is_active:
        return None

    # 查用户角色
    roles_result = db.execute(
        select(SysRole).join(SysUserRole, SysUserRole.role_id == SysRole.id)
        .where(SysUserRole.user_id == user_id, SysRole.is_deleted == False)
    ).scalars().all()

    role_codes = [r.code for r in roles_result]

    # 查角色权限
    if role_codes:
        perm_result = db.execute(
            select(SysPermission).join(
                SysRolePermission, SysRolePermission.permission_id == SysPermission.id
            ).join(SysRole, SysRole.id == SysRolePermission.role_id)
            .where(
                SysRole.code.in_(role_codes),
                SysPermission.is_deleted == False,
                SysRole.is_deleted == False,
            )
        ).scalars().all()
        perm_codes = [p.code for p in perm_result]
    else:
        perm_codes = []

    # 用户级直授权限(绕过角色, 例外/临时授权) — 与角色权限并集
    direct_result = db.execute(
        select(SysPermission).join(
            SysUserPermission, SysUserPermission.permission_id == SysPermission.id
        ).where(
            SysUserPermission.user_id == user_id,
            SysUserPermission.is_deleted == False,
            SysPermission.is_deleted == False,
        )
    ).scalars().all()
    if direct_result:
        seen = set(perm_codes)
        for p in direct_result:
            if p.code not in seen:
                seen.add(p.code)
                perm_codes.append(p.code)

    # 数据范围(随权限缓存一起缓存, 授权变更时通过 invalidate_user_permissions 失效)
    from app.services.data_scope_service import build_data_scope
    data_scope = build_data_scope(db, user.id, roles=role_codes).to_dict()

    return {
        "user_id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "department_id": user.department_id,
        "person_id": user.person_id,
        "roles": role_codes,
        "permissions": perm_codes,
        "data_scope": data_scope,
    }


def authenticate_user(db: Session, username: str, password: str) -> Optional[SysUser]:
    """验证用户名密码"""
    user = db.execute(
        select(SysUser).where(
            SysUser.username == username,
            SysUser.is_deleted == False,
            SysUser.is_active == True,
        )
    ).scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        return None
    return user
