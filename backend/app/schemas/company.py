from pydantic import BaseModel, Field
from typing import Optional
import datetime


class CompanyCreate(BaseModel):
    code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=256)
    short_name: Optional[str] = None
    company_type: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    industry: Optional[str] = None
    credit_code: Optional[str] = None
    credit_level: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    ext_attrs: Optional[dict] = None


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    company_type: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    industry: Optional[str] = None
    credit_code: Optional[str] = None
    credit_level: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    ext_attrs: Optional[dict] = None


class CompanyResponse(BaseModel):
    id: int
    code: str
    name: str
    short_name: Optional[str] = None
    company_type: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    industry: Optional[str] = None
    credit_code: Optional[str] = None
    credit_level: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    ext_attrs: Optional[dict] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    # 列表聚合展示字段(分项查询页依赖)
    bid_count: Optional[int] = 0
    qua_count: Optional[int] = 0
    credit_score: Optional[int] = None
    latest_bid_at: Optional[str] = None
    contact_phone: Optional[str] = None
    ownership: Optional[str] = None
    business_scope: Optional[str] = None
    establish_date: Optional[str] = None
    registered_capital: Optional[str] = None
    model_config = {"from_attributes": True}


class ProjectCompanyCreate(BaseModel):
    project_id: int
    company_id: int
    role: str = Field(..., max_length=64)
    stage: str = Field("", max_length=64, description="所属阶段(关联 project_progress_stage, 空=全程/不限)")
    joined_at: Optional[datetime.datetime] = None
    ext_attrs: Optional[dict] = None


class ProjectCompanyUpdate(BaseModel):
    role: Optional[str] = None
    stage: Optional[str] = Field(None, max_length=64, description="所属阶段")
    left_at: Optional[datetime.datetime] = None
    is_active: Optional[bool] = None
    ext_attrs: Optional[dict] = None


class ProjectCompanyResponse(BaseModel):
    id: int
    project_id: int
    company_id: int
    role: str
    stage: str = ""
    joined_at: datetime.datetime
    left_at: Optional[datetime.datetime] = None
    is_active: bool
    ext_attrs: Optional[dict] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = {"from_attributes": True}


class CompanyTimelineResponse(ProjectCompanyResponse):
    company_name: Optional[str] = None
    company_code: Optional[str] = None
    company_type: Optional[str] = None
