"""前台首页内容配置(CMS) — 支撑「首页配置中心」后台管理。

设计思路: 前台首页约 9 个静态展示模块(引导条/图标入口/资质/Banner/领域/
国际机构/产品/研讨/认证)均可用「区块 + 条目」两张通用表承载:
- CmsBlock     : 区块(block_key 唯一, 如 banner/quick_links/certs)
- CmsBlockItem : 区块条目(按 sort_order 排序, meta 存差异化字段: 颜色/日期/合作数等)

后台按区块管理, 前台通过 /public/home-config 一次性拉取启用的全部区块配置。
"""
from typing import Optional
from sqlalchemy import String, Integer, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class CmsBlock(BaseModel):
    """前台页面配置区块主表（page_key 区分所属前台页面）"""
    __tablename__ = "cms_block"

    page_key: Mapped[str] = mapped_column(
        String(32), nullable=False, default="home",
        comment="所属前台页面: home/about/contact/solutions/intelligence/datacenter",
    )
    block_key: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="区块标识(banner/quick_links/certs/cta/fields/partners/products/activities/certifications/recommends 等)"
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False, comment="区块标题")
    description: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="区块说明(供后台展示)")
    enabled: Mapped[int] = mapped_column(Integer, default=1, comment="是否启用:1启用 0停用")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="区块排序")
    extra: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, comment="区块级扩展配置(JSON)")


class CmsBlockItem(BaseModel):
    """区块条目(前台展示的具体内容)"""
    __tablename__ = "cms_block_item"

    block_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="所属区块 CmsBlock.id")
    item_key: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="条目标识(可选)")
    title: Mapped[str] = mapped_column(String(256), nullable=False, comment="条目标题/名称")
    subtitle: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="副标题/描述/子文案")
    icon: Mapped[Optional[str]] = mapped_column(String(128), default=None, comment="图标(Element Plus 图标名)")
    link: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="跳转地址")
    meta: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, comment="差异化字段(JSON: 颜色/日期/合作数/短码等)")
    enabled: Mapped[int] = mapped_column(Integer, default=1, comment="是否启用:1启用 0停用")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="展示排序")
