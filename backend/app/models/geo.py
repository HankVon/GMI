"""GEO 监测模块 ORM — AI 引擎配置 / 关键词任务 / 查询结果 / 营销配置"""
from typing import Optional
import datetime
from sqlalchemy import String, Boolean, BigInteger, DateTime, Text, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class GeoEngine(Base):
    """AI 引擎配置: 采集适配器 manual(手填)/crawl4ai(网页抓取)/openai_api(兼容API)"""

    __tablename__ = "geo_engine"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="primary key")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="引擎名称(豆包/DeepSeek/秘塔/百度AI搜索等)")
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="引擎编码")
    url: Mapped[Optional[str]] = mapped_column(String(1024), default=None, comment="网页访问地址")
    adapter: Mapped[str] = mapped_column(String(32), default="manual", comment="采集适配器: manual/crawl4ai/openai_api")
    api_endpoint: Mapped[Optional[str]] = mapped_column(String(1024), default=None, comment="OpenAI兼容API端点")
    api_key: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="API密钥")
    api_model: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="API模型名")
    notes: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="备注")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, comment="create time")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, comment="update time"
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="soft delete flag")


class GeoKeyword(Base):
    """监测关键词任务: 行业词×公司词矩阵, 绑定引擎, 定时执行"""

    __tablename__ = "geo_keyword"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="primary key")
    keyword: Mapped[str] = mapped_column(String(256), nullable=False, comment="监测关键词(问题)")
    region: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="地域限定")
    category: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="行业分类")
    engines: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="绑定引擎JSON数组(空=全部启用引擎)")
    priority: Mapped[int] = mapped_column(Integer, default=5, comment="优先级 1-10")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    last_run_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, default=None, comment="上次执行时间")

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, comment="create time")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, comment="update time"
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="soft delete flag")


class GeoMention(Base):
    """查询结果: AI 回答快照 + 引用来源 + 提及实体 + 品牌可见性"""

    __tablename__ = "geo_mention"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="primary key")
    engine_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="引擎id")
    engine_name: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="引擎名称快照")
    keyword_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="关键词任务id")
    keyword: Mapped[str] = mapped_column(String(256), nullable=False, comment="查询词快照")
    asked_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, comment="查询时间")
    adapter: Mapped[str] = mapped_column(String(32), default="manual", comment="采集方式 manual/crawl4ai/openai_api")
    answer_text: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="AI回答全文")
    raw_text: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="原始抓取文本")
    cited_sources: Mapped[Optional[list]] = mapped_column(JSON, default=None, comment="被引用来源 [{title,url,domain}]")
    mentioned_entities: Mapped[Optional[list]] = mapped_column(JSON, default=None, comment="提及实体 [{name,type}]")
    brand_hits: Mapped[Optional[list]] = mapped_column(JSON, default=None, comment="命中的品牌词")
    self_visible: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否提及本公司")
    self_rank: Mapped[int] = mapped_column(Integer, default=0, comment="本公司在回答中的提及位置(0=未提及)")
    summary: Mapped[Optional[str]] = mapped_column(String(1024), default=None, comment="LLM总结(一句话)")
    status: Mapped[str] = mapped_column(String(16), default="pending", comment="状态: pending/parsed/error")
    error: Mapped[Optional[str]] = mapped_column(String(1024), default=None, comment="错误信息")
    elapsed_ms: Mapped[Optional[int]] = mapped_column(Integer, default=None, comment="耗时(毫秒)")

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, comment="create time")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, comment="update time"
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="soft delete flag")


class MkConfig(Base):
    """营销配置键值表: brand_names/industry_keywords/content_style/geo_schedule"""

    __tablename__ = "mk_config"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="primary key")
    cfg_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="配置键")
    cfg_value: Mapped[Optional[str]] = mapped_column(Text, default=None, comment="配置值(JSON)")
    description: Mapped[Optional[str]] = mapped_column(String(256), default=None, comment="说明")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, comment="update time"
    )
