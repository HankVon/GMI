from pydantic import BaseModel, Field
from typing import Optional
import datetime


class PersonCreate(BaseModel):
    """创建人员"""
    code: str = Field(..., max_length=64, description="人员编码")
    name: str = Field(..., max_length=128, description="姓名")
    email: Optional[str] = None
    phone: Optional[str] = None
    department_id: Optional[int] = None
    company_id: Optional[int] = None
    position: Optional[str] = None
    status: str = Field(default="active", max_length=32)
    entry_date: Optional[datetime.date] = None
    resign_date: Optional[datetime.date] = None
    ext_attrs: Optional[dict] = None
    is_active: bool = True


class PersonUpdate(BaseModel):
    """更新人员"""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department_id: Optional[int] = None
    company_id: Optional[int] = None
    position: Optional[str] = None
    status: Optional[str] = None
    entry_date: Optional[datetime.date] = None
    resign_date: Optional[datetime.date] = None
    ext_attrs: Optional[dict] = None
    is_active: Optional[bool] = None


class PersonResponse(BaseModel):
    """人员响应"""
    id: int
    code: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    department_id: Optional[int] = None
    company_id: Optional[int] = None
    position: Optional[str] = None
    status: str
    entry_date: Optional[datetime.date] = None
    resign_date: Optional[datetime.date] = None
    ext_attrs: Optional[dict] = None
    is_active: bool = True
    created_at: datetime.datetime
    updated_at: datetime.datetime
    # 列表展示用: 关联公司名 / 最新参与项目发布时间 / 参与项目名列表
    company_name: Optional[str] = None
    latest_project_time: Optional[datetime.datetime] = None
    related_projects: Optional[str] = None

    model_config = {"from_attributes": True}
