from pydantic import BaseModel, Field
from typing import Optional
import datetime


class ProjectMemberCreate(BaseModel):
    """添加项目成员"""
    project_id: int = Field(..., description="项目ID")
    person_id: int = Field(..., description="人员ID")
    role: str = Field(..., max_length=64, description="项目角色:manager/member/observer")
    responsibility: Optional[str] = None
    stage: str = Field("", max_length=64, description="所属阶段(关联 project_progress_stage, 空=全程/不限)")
    joined_at: Optional[datetime.datetime] = None  # NULL=当前时间
    ext_attrs: Optional[dict] = None


class ProjectMemberUpdate(BaseModel):
    """更新项目成员(角色/职责/阶段/退出)"""
    role: Optional[str] = None
    responsibility: Optional[str] = None
    stage: Optional[str] = Field(None, max_length=64, description="所属阶段")
    left_at: Optional[datetime.datetime] = None  # 设为NULL或值
    is_active: Optional[bool] = None
    ext_attrs: Optional[dict] = None


class ProjectMemberResponse(BaseModel):
    """项目成员响应"""
    id: int
    project_id: int
    person_id: int
    role: str
    responsibility: Optional[str] = None
    stage: str = ""
    joined_at: datetime.datetime
    left_at: Optional[datetime.datetime] = None
    is_active: bool
    ext_attrs: Optional[dict] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class MemberTimelineResponse(ProjectMemberResponse):
    """项目成员时间线(含人员基本信息)"""
    person_name: Optional[str] = None
    person_code: Optional[str] = None
    person_department: Optional[str] = None
    person_position: Optional[str] = None
    company_id: Optional[int] = None
    company_name: Optional[str] = None
