from pydantic import BaseModel, Field
from typing import Optional
import datetime


class ProjectProgressCreate(BaseModel):
    project_id: int
    title: str = Field(..., max_length=256)
    content: Optional[str] = None
    progress_date: datetime.datetime
    sort_order: int = 0


class ProjectProgressUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=256)
    content: Optional[str] = None
    progress_date: Optional[datetime.datetime] = None
    sort_order: Optional[int] = None


class ProjectProgressResponse(BaseModel):
    id: int
    project_id: int
    title: str
    content: Optional[str] = None
    progress_date: datetime.datetime
    sort_order: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}
