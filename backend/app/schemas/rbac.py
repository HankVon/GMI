from pydantic import BaseModel, Field
from typing import Optional
import datetime


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., max_length=64)
    password: str = Field(..., max_length=128)


class TokenResponse(BaseModel):
    """Token响应"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserBrief"


class UserBrief(BaseModel):
    """用户简要信息"""
    id: int
    username: str
    display_name: str
    email: Optional[str] = None
    department_id: Optional[int] = None
    roles: list[str] = []
    permissions: list[str] = []


class UserCreate(BaseModel):
    """创建用户"""
    username: str = Field(..., max_length=64)
    password: str = Field(..., max_length=128)
    display_name: str = Field(..., max_length=128)
    email: Optional[str] = None
    phone: Optional[str] = None
    department_id: Optional[int] = None
    role_ids: list[int] = Field(default_factory=list)


class RoleCreate(BaseModel):
    """创建角色"""
    code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=128)
    description: Optional[str] = None
    permission_ids: list[int] = Field(default_factory=list)
