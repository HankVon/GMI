"""JWT 认证中间件"""
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth_service import decode_access_token, get_user_with_permissions
from app.services.cache_service import cache_service

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    """获取当前登录用户(含角色+权限)"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭证",
        )

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="凭证无效或已过期",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="凭证格式错误")

    # 先查缓存
    cached = await cache_service.get_user_permissions(int(user_id))
    if cached:
        return cached

    # 回源DB
    user_data = get_user_with_permissions(db, int(user_id))
    if not user_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")

    # 写入缓存
    await cache_service.set_user_permissions(int(user_id), user_data)
    return user_data


def require_permission(permission_code: str):
    """权限校验依赖工厂"""

    async def _check(
        user: dict = Depends(get_current_user),
    ):
        if permission_code not in user.get("permissions", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"无 '{permission_code}' 权限",
            )
        return user

    return _check


def require_any_permission(*permission_codes: str):
    """多权限(满足任一即可)校验依赖工厂"""

    async def _check(
        user: dict = Depends(get_current_user),
    ):
        user_perms = user.get("permissions", [])
        if not any(p in user_perms for p in permission_codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"无 {permission_codes} 中任一权限",
            )
        return user

    return _check
