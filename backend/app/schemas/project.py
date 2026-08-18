from pydantic import BaseModel, Field
from typing import Optional
import datetime


class ProjectCreate(BaseModel):
    """创建项目"""
    code: str = Field(..., max_length=64, description="项目编码")
    name: str = Field(..., max_length=256, description="项目名称")
    description: Optional[str] = None
    status: str = Field(default="active", max_length=32)
    manager_id: Optional[int] = None
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None
    department_id: Optional[int] = None
    ext_attrs: Optional[dict] = None  # 动态字段JSON
    is_active: bool = True


class ProjectUpdate(BaseModel):
    """更新项目"""
    name: Optional[str] = Field(None, max_length=256)
    description: Optional[str] = None
    status: Optional[str] = None
    manager_id: Optional[int] = None
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None
    department_id: Optional[int] = None
    ext_attrs: Optional[dict] = None  # 动态字段JSON(合并更新)
    is_active: Optional[bool] = None


class ProjectResponse(BaseModel):
    """项目响应"""
    id: int
    code: str
    name: str
    description: Optional[str] = None
    status: str
    manager_id: Optional[int] = None
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None
    department_id: Optional[int] = None
    ext_attrs: Optional[dict] = None
    is_active: bool = True
    created_at: datetime.datetime
    updated_at: datetime.datetime
    # 最近一次项目进展日期(来自 project_progress, 列表页展示「更新时间」)
    last_progress_date: Optional[datetime.datetime] = None
    # 最近一次项目进展标题(来自 project_progress, 列表页展示「项目阶段」)
    last_progress_title: Optional[str] = None
    # 项目所在省市(取关联单位 company 的 province/city, 列表页展示「省份城市」)
    province_city: Optional[str] = None
    # 合同/项目金额(来自 ext_attrs.amount, 列表页「总投资额」/详情页「金额」)
    amount: Optional[str] = None

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        """重载: 从 ext_attrs 提取 amount, 供列表/详情统一使用。"""
        item = super().model_validate(obj, *args, **kwargs)
        ext = obj.ext_attrs or {}
        if not item.amount and ext.get("amount"):
            item.amount = str(ext["amount"])
        return item
