"""标讯后台管理 Schema — 与前台 TenderDetailData 契约对齐。

后台录入/编辑采用「扁平 + 分组」嵌套结构:
  - 高频筛选列冗余到 bid_notice 独立列(标题/类型/分类/行业/地域/采购人/预算区间/发布时间/状态)
  - 结构化明细写入 meta JSON(project_info/finance/evaluation/requirements/timeline/suppliers/body),
    与前台 TenderDetailService 读取路径完全一致, 保证详情页零改动即可展示后台录入的数据。
"""
from typing import Any, Optional
import datetime
from pydantic import BaseModel, Field


class ProjectInfoPayload(BaseModel):
    """项目概况(对应前台 KV 网格 + 时间矩阵)"""
    code: Optional[str] = Field(default=None, description="项目编号")
    type: Optional[str] = Field(default=None, description="项目类型(设计 施工)")
    scale: Optional[str] = Field(default=None, description="建设规模")
    scope: Optional[str] = Field(default=None, description="招标范围")
    duration: Optional[str] = Field(default=None, description="建设工期")
    method: Optional[str] = Field(default=None, description="招标方式")
    registration_deadline: Optional[str] = Field(default=None, description="报名截止")
    document_deadline: Optional[str] = Field(default=None, description="文件获取截止")
    bid_deadline: Optional[str] = Field(default=None, description="投标截止")
    opening_time: Optional[str] = Field(default=None, description="开标时间")


class FinanceInfoPayload(BaseModel):
    """资金信息"""
    budget: Optional[str] = Field(default=None, description="预算金额展示文本")
    source: Optional[str] = Field(default=None, description="资金来源")


class EvaluationInfoPayload(BaseModel):
    """评标信息"""
    method: Optional[str] = Field(default=None, description="评标办法")


class RequirementsInfoPayload(BaseModel):
    """资质/业绩要求"""
    qualification: Optional[str] = Field(default=None, description="资格审查")
    consortium: Optional[str] = Field(default=None, description="联合体要求")


class TimelineEventPayload(BaseModel):
    """招标进度事件"""
    label: Optional[str] = Field(default=None, description="事件名称")
    date: Optional[str] = Field(default=None, description="日期")
    summary: Optional[str] = Field(default=None, description="摘要/说明")


class SupplierPayload(BaseModel):
    """中标供应商"""
    supplier: Optional[str] = Field(default=None, description="供应商名称")
    supplier_company_id: Optional[int] = Field(default=None, description="匹配公司 id")
    amount: Optional[float] = Field(default=None, description="中标金额(元)")
    address: Optional[str] = Field(default=None, description="地址")


class BidCreatePayload(BaseModel):
    """标讯录入/编辑统一载荷(编辑时全部字段可选覆盖)"""

    # 基础
    title: str = Field(..., min_length=1, max_length=512, description="公告标题")
    url: Optional[str] = Field(default=None, max_length=1024, description="原文链接")
    notice_type: Optional[str] = Field(default=None, max_length=64, description="公告类型")
    category: Optional[str] = Field(default=None, max_length=64, description="项目分类(工程/服务/货物)")
    industry: Optional[str] = Field(default=None, max_length=128, description="行业类型")
    region: Optional[str] = Field(default=None, max_length=128, description="项目地区")
    purchaser: Optional[str] = Field(default=None, max_length=512, description="招标单位")
    purchaser_company_id: Optional[int] = Field(default=None, description="匹配公司 id")
    agency: Optional[str] = Field(default=None, max_length=512, description="招标代理")
    source_id: Optional[int] = Field(default=None, description="来源站点 id")
    source_name: Optional[str] = Field(default=None, max_length=128, description="来源名称")
    published_at: Optional[datetime.datetime] = Field(default=None, description="发布时间")
    purchase_way: Optional[str] = Field(default=None, max_length=64, description="采购方式")
    price_type: Optional[str] = Field(default=None, max_length=32, description="询价方式")
    budget_min: Optional[float] = Field(default=None, ge=0, description="预算下限(万元)")
    budget_max: Optional[float] = Field(default=None, ge=0, description="预算上限(万元)")

    # 结构化明细 → meta
    project: ProjectInfoPayload = Field(default_factory=ProjectInfoPayload)
    finance: FinanceInfoPayload = Field(default_factory=FinanceInfoPayload)
    evaluation: EvaluationInfoPayload = Field(default_factory=EvaluationInfoPayload)
    requirements: RequirementsInfoPayload = Field(default_factory=RequirementsInfoPayload)
    keywords: list[str] = Field(default_factory=list)
    timeline: list[TimelineEventPayload] = Field(default_factory=list)
    suppliers: list[SupplierPayload] = Field(default_factory=list)
    body: Optional[str] = Field(default=None, description="公告正文")


class BidUpdatePayload(BaseModel):
    """编辑载荷 — 可部分提交(按需覆盖, None 字段忽略)"""
    title: Optional[str] = Field(default=None, min_length=1, max_length=512)
    url: Optional[str] = Field(default=None, max_length=1024)
    notice_type: Optional[str] = Field(default=None, max_length=64)
    category: Optional[str] = Field(default=None, max_length=64)
    industry: Optional[str] = Field(default=None, max_length=128)
    region: Optional[str] = Field(default=None, max_length=128)
    purchaser: Optional[str] = Field(default=None, max_length=512)
    purchaser_company_id: Optional[int] = Field(default=None)
    agency: Optional[str] = Field(default=None, max_length=512)
    source_id: Optional[int] = Field(default=None)
    source_name: Optional[str] = Field(default=None, max_length=128)
    published_at: Optional[datetime.datetime] = Field(default=None)
    purchase_way: Optional[str] = Field(default=None, max_length=64)
    price_type: Optional[str] = Field(default=None, max_length=32)
    budget_min: Optional[float] = Field(default=None, ge=0)
    budget_max: Optional[float] = Field(default=None, ge=0)
    project: Optional[ProjectInfoPayload] = Field(default=None)
    finance: Optional[FinanceInfoPayload] = Field(default=None)
    evaluation: Optional[EvaluationInfoPayload] = Field(default=None)
    requirements: Optional[RequirementsInfoPayload] = Field(default=None)
    keywords: Optional[list[str]] = Field(default=None)
    timeline: Optional[list[TimelineEventPayload]] = Field(default=None)
    suppliers: Optional[list[SupplierPayload]] = Field(default=None)
    body: Optional[str] = Field(default=None)


class ReviewPayload(BaseModel):
    """审核载荷"""
    approve: bool = Field(..., description="true=通过 false=驳回")
    comment: Optional[str] = Field(default=None, max_length=512, description="审核意见")


class OfflinePayload(BaseModel):
    """下架载荷"""
    reason: Optional[str] = Field(default=None, max_length=512, description="下架原因")


class BatchPayload(BaseModel):
    """批量操作载荷"""
    ids: list[int] = Field(..., min_length=1)
    action: str = Field(..., description="delete/publish/offline/submit")
