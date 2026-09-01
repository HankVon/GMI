"""网页线索筛选器 — 只有通过筛选的网页才入库。

筛选规则(来自 WebSource 配置):
  1. 域名白名单: 网页 URL 域名必须在 allow_domains 内(空=不限制)
  2. 命中关键词: 标题/摘要/正文 至少命中一个 keywords(空=不限制)
  3. 排除关键词: 命中 exclude_keywords 则丢弃
  4. 地域限定: 正文命中 regions 中的地域词(可选)
"""
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse


@dataclass
class ClueFilterResult:
    """筛选结果: passed=True 才入库"""

    passed: bool
    reason: str = ""  # 拒绝原因
    hit_keywords: list[str] = field(default_factory=list)
    region: Optional[str] = None
    category: Optional[str] = None


def _split_csv(text: Optional[str]) -> list[str]:
    if not text:
        return []
    return [t.strip() for t in text.split(",") if t and t.strip()]


def _extract_domain(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
        # 去掉 www. 前缀便于白名单匹配
        return host[4:] if host.startswith("www.") else host
    except Exception:  # noqa: BLE001
        return ""


class ClueFilter:
    """按来源配置对单个网页做筛选。"""

    def __init__(
        self,
        allow_domains: str = "",
        keywords: str = "",
        exclude_keywords: str = "",
        regions: str = "",
    ):
        self.allow_domains = [d.strip().lower() for d in _split_csv(allow_domains)]
        self.keywords = _split_csv(keywords)
        self.exclude_keywords = _split_csv(exclude_keywords)
        self.regions = _split_csv(regions)

    def filter(
        self,
        url: str,
        title: str = "",
        markdown: str = "",
    ) -> ClueFilterResult:
        # 1. 域名白名单(支持子域: 配置父域即允许其下所有子域)
        domain = _extract_domain(url)
        if self.allow_domains:
            allowed = any(domain == d or domain.endswith("." + d) for d in self.allow_domains)
            if not allowed:
                return ClueFilterResult(False, reason=f"域名不在白名单: {domain}")

        text_block = f"{title}\n{markdown}"[:20000]

        # 2. 排除关键词(命中即丢弃)
        for kw in self.exclude_keywords:
            if kw.lower() in text_block.lower():
                return ClueFilterResult(False, reason=f"命中排除关键词: {kw}")

        # 3. 命中关键词(至少一个)
        hits = [kw for kw in self.keywords if kw.lower() in text_block.lower()]
        if self.keywords and not hits:
            return ClueFilterResult(False, reason="未命中任何关键词")

        # 4. 地域
        region = None
        for r in self.regions:
            if r.lower() in text_block.lower():
                region = r
                break

        return ClueFilterResult(
            passed=True,
            hit_keywords=hits,
            region=region,
            category=None,
        )
