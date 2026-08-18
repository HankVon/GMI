"""Pydantic v2 共享 Schema 组件"""
from pydantic import BaseModel, Field
from typing import Optional, Any
import datetime


class PaginatedParams(BaseModel):
    """分页请求参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class PaginatedResponse(BaseModel):
    """分页响应"""
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页条数")
    items: list[Any] = Field(description="数据列表")


class APIResponse(BaseModel):
    """统一API响应"""
    success: bool = True
    message: str = "OK"
    data: Any = None


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    message: str = ""
    error_code: Optional[str] = None
    detail: Any = None
