"""前台首页内容配置(CMS) Schema"""
from typing import Optional, Any
from pydantic import BaseModel, Field


class CmsBlockItemSchema(BaseModel):
    """区块条目 Schema"""
    id: Optional[int] = None
    item_key: Optional[str] = Field(default=None, max_length=128)
    title: str = Field(max_length=256)
    subtitle: Optional[str] = Field(default=None, max_length=512)
    icon: Optional[str] = Field(default=None, max_length=128)
    link: Optional[str] = Field(default=None, max_length=512)
    meta: Optional[dict] = Field(default=dict)
    enabled: int = Field(default=1, ge=0, le=1)
    sort_order: int = Field(default=0)


class CmsBlockItemCreate(BaseModel):
    """创建区块条目请求"""
    item_key: Optional[str] = Field(default=None, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    subtitle: Optional[str] = Field(default=None, max_length=512)
    icon: Optional[str] = Field(default=None, max_length=128)
    link: Optional[str] = Field(default=None, max_length=512)
    meta: Optional[dict] = Field(default=dict)
    enabled: int = Field(default=1, ge=0, le=1)
    sort_order: int = Field(default=0)


class CmsBlockItemUpdate(BaseModel):
    """更新区块条目请求(仅传需要修改的字段)"""
    item_key: Optional[str] = Field(default=None, max_length=128)
    title: Optional[str] = Field(default=None, max_length=256)
    subtitle: Optional[str] = Field(default=None, max_length=512)
    icon: Optional[str] = Field(default=None, max_length=128)
    link: Optional[str] = Field(default=None, max_length=512)
    meta: Optional[dict] = None
    enabled: Optional[int] = Field(default=None, ge=0, le=1)
    sort_order: Optional[int] = Field(default=None)


class CmsBlockCreate(BaseModel):
    """创建区块请求"""
    page_key: str = Field(default="home", min_length=1, max_length=32)
    block_key: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=256)
    description: Optional[str] = Field(default=None, max_length=512)
    enabled: int = Field(default=1, ge=0, le=1)
    sort_order: int = Field(default=0)
    extra: Optional[dict] = Field(default=dict)


class CmsBlockUpdate(BaseModel):
    """更新区块请求(仅传需要修改的字段)"""
    title: Optional[str] = Field(default=None, max_length=256)
    description: Optional[str] = Field(default=None, max_length=512)
    enabled: Optional[int] = Field(default=None, ge=0, le=1)
    sort_order: Optional[int] = Field(default=None)
    extra: Optional[dict] = None
