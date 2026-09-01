"""标讯详情页稳定数据契约。暂不启用会员制，is_gated 当前由服务配置为 False。"""
from typing import Any, Optional
from pydantic import BaseModel, Field


class DisplayField(BaseModel):
    value: Any = None
    displayText: str = "未披露"
    isGated: bool = False


class EntityLink(BaseModel):
    entityId: Optional[int] = None
    entityType: str = "company"
    name: str
    href: Optional[str] = None
    matched: bool = False


class DetailTag(BaseModel):
    label: str
    kind: str = Field(pattern="^(status|category|warning)$")
    displayText: Optional[str] = None
    isGated: bool = False


class DetailHeader(BaseModel):
    id: int
    title: str
    projectCode: Optional[str] = None
    publishedAt: str = ""
    sourceName: Optional[str] = None
    sourceUrl: Optional[str] = None


class DetailKvItem(BaseModel):
    label: str
    field: DisplayField
    entity: Optional[EntityLink] = None
    wide: bool = False


class TimelineEvent(BaseModel):
    name: str
    date: Optional[str] = None
    summary: DisplayField = Field(default_factory=DisplayField)


class SupplierItem(BaseModel):
    """中标/成交供应商。

    此前 TenderDetailData 遗漏该字段, 导致中标公告在聚合详情接口里
    丢失中标供应商与成交金额(标讯 383 即为此情况)。
    """

    name: str = ""
    address: Optional[str] = None
    amount: Optional[float] = None
    amount_text: Optional[str] = None
    score: Optional[float] = None
    companyId: Optional[int] = None
    rank: int = 0


class TenderActionState(BaseModel):
    canDownload: bool = True
    isMonitored: bool = False
    isCollected: bool = False


class TenderDetailData(BaseModel):
    header: DetailHeader
    tags: list[DetailTag] = Field(default_factory=list)
    kv: list[DetailKvItem] = Field(default_factory=list)
    timeMatrix: list[DetailKvItem] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    suppliers: list[SupplierItem] = Field(default_factory=list)
    body: str = ""
    attachments: list[Any] = Field(default_factory=list)
    # 正文补抽结果(清洗后正文 + 标量字段 + 时间节点 + 中标结果 + 更正内容 + 附件线索)
    enriched: dict[str, Any] = Field(default_factory=dict)
    relatedCompanies: list[EntityLink] = Field(default_factory=list)
    entities: dict[str, Optional[EntityLink]] = Field(default_factory=dict)
    actions: TenderActionState = Field(default_factory=TenderActionState)
