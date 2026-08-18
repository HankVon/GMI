"""来源站点配置 — crawl4ai 定时爬取的数据源"""
from typing import Optional
import datetime
from sqlalchemy import String, Boolean, BigInteger, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WebSource(Base):
    """网页线索来源站点: 配置抓取地址 + 域名白名单 + 抓取规则"""

    __tablename__ = "web_source"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="primary key")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="来源名称(如:四川省公共资源交易中心)")
    url: Mapped[str] = mapped_column(String(1024), nullable=False, comment="来源 URL(列表页/种子页)")
    description: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="来源说明")

    # 筛选规则
    allow_domains: Mapped[str] = mapped_column(Text, default="", comment="域名白名单(逗号分隔, 空=不限制域名)")
    keywords: Mapped[str] = mapped_column(Text, default="", comment="命中关键词(逗号分隔)")
    exclude_keywords: Mapped[str] = mapped_column(Text, default="", comment="排除关键词(逗号分隔)")
    regions: Mapped[str] = mapped_column(Text, default="", comment="地域限定(逗号分隔, 空=不限)")

    # 抓取行为
    scrape_mode: Mapped[str] = mapped_column(String(32), default="crawl", comment="抓取模式: scrape单页 / crawl整站 / query查询式")
    max_depth: Mapped[int] = mapped_column(BigInteger, default=1, comment="crawl 最大深度")
    max_pages: Mapped[int] = mapped_column(BigInteger, default=50, comment="crawl 最多页数")
    include_urls: Mapped[str] = mapped_column(Text, default="", comment="仅抓取匹配的 URL 模式(可选)")
    # 查询式抓取配置(JSON, scrape_mode=query 时生效)
    query_config: Mapped[str] = mapped_column(Text, default="{}", comment="查询式抓取配置 JSON: captcha_placeholder/query_button_text/captcha_img_keyword/api_url_keyword/result_rows_jsonpath/captcha_refresh_keyword")
    # LLM 增强: filter(仅AI筛选, 默认) / extract / summary / all / ""(关闭)
    llm_enhance: Mapped[str] = mapped_column(String(32), default="filter", comment="LLM 增强模式: filter/extract/summary/all/空=关闭")

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    last_run_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, default=None, comment="上次抓取时间")
    last_run_result: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="上次抓取结果摘要")
    last_error: Mapped[Optional[str]] = mapped_column(String(1024), default=None, comment="上次抓取错误")

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, comment="create time")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now, comment="update time"
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="soft delete flag")
