"""认证与 RBAC 管理 API"""
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.rbac import SysUser
from app.middleware.auth import get_current_user, require_permission
from app.services.auth_service import (
    authenticate_user, create_access_token, hash_password,
    get_user_with_permissions,
)
from app.services.rate_limit import (
    check_login_rate_limit, record_login_failure, record_login_success,
)
from app.schemas.rbac import LoginRequest, TokenResponse, UserBrief
from app.config import settings

router = APIRouter(tags=["认证与授权"])

# 密码强度: 8-64 位, 须同时包含字母和数字(防弱口令被暴力破解)
_PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9@#$%^&+=!_\-.*~]{8,64}$")


def _validate_password_strength(password: str) -> None:
    """密码强度校验(注册/改密时调用)。"""
    if not _PASSWORD_RE.match(password or ""):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码强度不足: 长度 8-64 位, 且须同时包含字母和数字",
        )


@router.post("/auth/login", response_model=TokenResponse)
async def login(request: Request, data: LoginRequest, db: Session = Depends(get_db)):
    """
    用户登录 — 返回JWT

    请求示例:
      ```json
      {"username": "admin", "password": "admin123"}
      ```

    响应示例:
      ```json
      {
        "access_token": "eyJhbGciOi...",
        "token_type": "bearer",
        "expires_in": 28800,
        "user": {
          "id": 1, "username": "admin", "display_name": "系统管理员",
          "department_id": 1,
          "roles": ["admin"], "permissions": ["api_project_crud", ...]
        }
      }
      ```
    """
    client_ip = request.client.host if request.client else None
    # 登录前检查限速(失败次数超阈值 → 429)
    check_login_rate_limit(client_ip)

    user = authenticate_user(db, data.username, data.password)
    if not user:
        record_login_failure(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    # 登录成功清零失败计数
    record_login_success(client_ip)
    user_data = get_user_with_permissions(db, user.id)

    token = create_access_token(
        data={
            "sub": str(user.id),
            "username": user.username,
        }
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserBrief(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            email=user.email,
            department_id=user.department_id,
            roles=user_data["roles"] if user_data else [],
            permissions=user_data["permissions"] if user_data else [],
        ),
    )


@router.get("/auth/me", response_model=UserBrief)
async def get_me(user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserBrief(
        id=user["user_id"],
        username=user["username"],
        display_name=user.get("display_name", ""),
        department_id=user.get("department_id"),
        roles=user.get("roles", []),
        permissions=user.get("permissions", []),
    )


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register_user(
    data: LoginRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_rbac")),
):
    """注册新用户"""
    from sqlalchemy import select

    # 密码强度校验(弱密码拒绝)
    _validate_password_strength(data.password)

    existing = db.execute(
        select(SysUser).where(SysUser.username == data.username)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在")

    new_user = SysUser(
        username=data.username,
        password_hash=hash_password(data.password),
        display_name=data.username,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"id": new_user.id, "username": new_user.username}
