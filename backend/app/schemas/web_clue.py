"""网页线索/来源站点 Schema"""
from typing import Optional
import datetime
from pydantic import BaseModel, Field


# ---------- WebSource ----------
class WebSourceCreate(BaseModel):
    name: str = Field(..., max_length=128)
    url: str = Field(..., max_length=1024)
    description: Optional[str] = None
    allow_domains: Optional[str] = ""
    keywords: Optional[str] = ""
    exclude_keywords: Optional[str] = ""
    regions: Optional[str] = ""
    scrape_mode: str = Field("crawl", max_length=32)
    max_depth: int = Field(1, ge=0, le=10)
    max_pages: int = Field(50, ge=1, le=1000)
    include_urls: Optional[str] = ""
    query_config: Optional[dict] = Field(None, description="查询式抓取配置 JSON(dict)")
    llm_enhance: Optional[str] = Field("filter", max_length=32, description="LLM 增强模式: filter/extract/summary/all/空=关闭")
    enabled: bool = True


class WebSourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    allow_domains: Optional[str] = None
    keywords: Optional[str] = None
    exclude_keywords: Optional[str] = None
    regions: Optional[str] = None
    scrape_mode: Optional[str] = None
    max_depth: Optional[int] = None
    max_pages: Optional[int] = None
    include_urls: Optional[str] = None
    query_config: Optional[dict] = None
    llm_enhance: Optional[str] = None
    enabled: Optional[bool] = None


class WebSourceResponse(BaseModel):
    id: int
    name: str
    url: str
    description: Optional[str] = None
    allow_domains: Optional[str] = ""
    keywords: Optional[str] = ""
    exclude_keywords: Optional[str] = ""
    regions: Optional[str] = ""
    scrape_mode: str
    max_depth: int
    max_pages: int
    include_urls: Optional[str] = ""
    query_config: Optional[dict] = Field(None, description="查询式抓取配置 JSON(dict)")
    llm_enhance: Optional[str] = Field("filter", max_length=32, description="LLM 增强模式")
    enabled: bool
    last_run_at: Optional[datetime.datetime] = None
    last_run_result: Optional[str] = None
    last_error: Optional[str] = None

    model_config = {"from_attributes": True}


class WebClueBatchDelete(BaseModel):
    ids: list[int] = Field(..., min_length=1, description="线索 ID 列表")


class WebClueEnhanceRequest(BaseModel):
    ids: list[int] = Field(..., min_length=1, description="线索 ID 列表")
    mode: str = Field("summary", description="增强模式: summary/extract/all")


# ---------- WebClue ----------
class WebClueResponse(BaseModel):
    id: int
    url: str
    title: str
    summary: Optional[str] = None
    content: Optional[str] = None
    source_id: Optional[int] = None
    source_name: Optional[str] = None
    hit_keywords: Optional[str] = None
    region: Optional[str] = None
    category: Optional[str] = None
    status: str
    published_at: Optional[datetime.datetime] = None
    fetched_at: datetime.datetime
    meta: Optional[dict] = Field(None, description="扩展信息(公告结构化字段: 截止/开标时间/预算/采购人/代理/地域等)")
    derived: Optional[list] = Field(None, description="线索派生实体明细(项目/单位/人员): [{entity_type,id,name,code}]")

    model_config = {"from_attributes": True}


class ManualCrawlRequest(BaseModel):
    """手动提交一批 URL 抓取并筛选"""
    urls: list[str] = Field(..., min_length=1, max_length=50)
    source_id: Optional[int] = None
    source_name: Optional[str] = None
    keywords: Optional[str] = ""
    exclude_keywords: Optional[str] = ""
    regions: Optional[str] = ""
