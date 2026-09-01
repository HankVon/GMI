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
from pydantic import BaseModel, Field
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
async def get_me(user: dict = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """获取当前用户信息(从DB读取完整资料)"""
    from sqlalchemy import select
    row = db.execute(
        select(SysUser).where(SysUser.id == user["user_id"], SysUser.is_deleted == False)
    ).scalar_one_or_none()
    return UserBrief(
        id=user["user_id"],
        username=user["username"],
        display_name=(row.display_name if row else user.get("display_name", "")),
        email=(row.email if row else None),
        phone=(row.phone if row else None),
        department_id=(row.department_id if row else user.get("department_id")),
        person_id=(row.person_id if row else None),
        roles=user.get("roles", []),
        permissions=user.get("permissions", []),
    )


# ── 个人中心: 改资料 / 改密码 ──
@router.put("/me/profile")
async def update_my_profile(
    body: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """当前用户修改自己的资料(显示名/邮箱/手机号)"""
    from sqlalchemy import select
    row = db.execute(
        select(SysUser).where(SysUser.id == user["user_id"], SysUser.is_deleted == False)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    if body.get("display_name") is not None:
        row.display_name = str(body["display_name"]).strip() or row.username
    if body.get("email") is not None:
        row.email = body["email"] or None
    if body.get("phone") is not None:
        row.phone = body["phone"] or None
    db.commit()
    # 刷新缓存里的展示名等
    from app.services.cache_service import cache_service
    await cache_service.invalidate_user_permissions(row.id)
    return {"success": True, "message": "ok"}


@router.put("/me/password")
async def change_my_password(
    body: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """当前用户修改密码(校验旧密码)"""
    from sqlalchemy import select
    from app.services.auth_service import verify_password
    row = db.execute(
        select(SysUser).where(SysUser.id == user["user_id"], SysUser.is_deleted == False)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    old_pwd = body.get("old_password", "")
    if not verify_password(old_pwd, row.password_hash):
        raise HTTPException(status_code=400, detail="原密码不正确")
    new_pwd = body.get("new_password", "")
    _validate_password_strength(new_pwd)
    row.password_hash = hash_password(new_pwd)
    db.commit()
    return {"success": True, "message": "密码修改成功"}


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=32)
    password: str = Field(..., min_length=8, max_length=64)
    display_name: str = Field(default="", max_length=32)
    email: str = Field(default="", max_length=64)
    phone: str = Field(default="", max_length=32)
    department_id: int | None = None
    role_ids: list[int] = Field(default_factory=list)
    data_scope_rule: str | None = Field(default=None, description="用户级数据范围:ALL/DEPT_TREE/DEPT_ONLY/OWN/CUSTOM")
    scope_dept_ids: list[int] = Field(default_factory=list, description="部门范围ID列表")


def _validate_scope_rule(rule: str | None) -> str | None:
    """校验数据范围规则, 非法返回 None。"""
    if not rule:
        return None
    rule = rule.strip().upper()
    allowed = ("ALL", "DEPT_TREE", "DEPT_ONLY", "OWN", "CUSTOM")
    return rule if rule in allowed else None


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register_user(
    data: RegisterRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_rbac")),
):
    """创建新账号(管理员分发账号): 支持 display_name/email/phone/部门/初始角色/数据范围"""
    from sqlalchemy import select
    from app.models.rbac import SysUserRole

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
        display_name=data.display_name or data.username,
        email=data.email or None,
        phone=data.phone or None,
        department_id=data.department_id,
    )
    # 数据范围(默认不启用, 不干扰现有行为)
    new_user.data_scope_rule = _validate_scope_rule(data.data_scope_rule)
    if new_user.data_scope_rule:
        new_user.scope_dept_ids = [d for d in data.scope_dept_ids if d] or None
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 分配初始角色
    import datetime
    for rid in data.role_ids:
        db.add(SysUserRole(user_id=new_user.id, role_id=rid, created_at=datetime.datetime.now()))
    db.commit()

    return {"id": new_user.id, "username": new_user.username}
