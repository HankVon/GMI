"""Crawl4AI 客户端 — 调用本地 crawl4ai 精简 HTTP 服务(11235 端口)

crawl4ai 需要 Python >=3.10, 而 SSM 后端运行在 Python 3.9, 因此 crawl4ai
以独立 HTTP 服务进程运行(crawl4ai-server/crawl4ai_server.py), 后端通过
HTTP 调用, 接口与之前 firecrawl 客户端保持兼容。

  POST /scrape  -> { url, title, markdown, published_at }
  POST /crawl   -> { data: [ {url,title,markdown,published_at,meta} ] }

用法(示例):
  client = Crawl4aiClient()
  result = await client.scrape("https://example.com")
"""
import asyncio
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger("crawl4ai")


class Crawl4aiError(Exception):
    """crawl4ai 服务调用异常"""


class Crawl4aiClient:
    """轻量封装 crawl4ai 服务的 scrape / crawl 接口(HTTP 同步, 调用方按需 await 线程池)。"""

    def __init__(self, base_url: Optional[str] = None, api_key: str = ""):
        self.base_url = (base_url or settings.CRAWL4AI_API_URL).rstrip("/")
        self.api_key = api_key or settings.CRAWL4AI_API_KEY

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _post(self, path: str, payload: dict, timeout: float = 600.0) -> dict:
        """默认 600s(10分钟) — query 模式多关键词检索耗时较长(7 关键词 × 逐详情)。"""
        url = f"{self.base_url}{path}"
        try:
            resp = httpx.post(url, json=payload, headers=self._headers(), timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.warning("[crawl4ai] %s failed status=%s body=%s", path, e.response.status_code, e.response.text[:300])
            raise Crawl4aiError(f"crawl4ai {path} HTTP {e.response.status_code}: {e.response.text[:200]}") from e
        except httpx.HTTPError as e:
            logger.warning("[crawl4ai] %s network error: %s", path, e)
            raise Crawl4aiError(f"crawl4ai 不可达({self.base_url}): {e}") from e
        if not data.get("success", True) and "detail" in data:
            logger.warning("[crawl4ai] %s api error: %s", path, data)
            raise Crawl4aiError(f"crawl4ai {path} error: {data.get('detail')}")
        return data

    def scrape(self, url: str, max_depth: int = 1) -> dict:
        """抓取单页, 返回 { url, title, markdown, published_at }"""
        data = self._post("/scrape", {"url": url, "max_depth": max_depth})
        return {
            "url": data.get("url") or url,
            "title": data.get("title") or url,
            "markdown": data.get("markdown") or "",
            "published_at": data.get("published_at"),
            "meta": data.get("meta"),
        }

    def crawl(self, url: str, max_depth: int = 1, max_pages: int = 50, include_urls: str = "") -> dict:
        """整站抓取, 返回 { data: [ {url,title,markdown,published_at,meta} ] }"""
        return self._post("/crawl", {
            "url": url,
            "max_depth": max_depth,
            "max_pages": max_pages,
            "include_urls": include_urls,
        })

    def query_crawl(self, url: str, query_config: Optional[dict] = None, max_pages: int = 3,
                    search_keywords: Optional[str] = None, task_id: Optional[str] = None,
                    timeout: float = 900.0, batch_index: Optional[int] = None,
                    batch_total: Optional[int] = None) -> dict:
        """查询式抓取(JS 渲染 + 验证码 OCR + 可选关键词检索)。

        针对公告列表 SPA 站点(如四川政府采购网): 打开页面 -> OCR 识别验证码
        -> 填表点查询(可填「标题」搜索框) -> 等接口返回 JSON -> 解析公告列表。
        search_keywords: 逗号分隔, 逐个填入搜索框检索并合并去重。
        query_config 支持 purchaser_placeholder: 填入「采购人」搜索框, 按单位名精准检索公告。
        task_id: 可选, 透传给 crawl4ai 服务用于查询实时进度(/query-progress/{task_id})。
        timeout: 单次 httpx 超时(秒), 默认 900s(15 分钟) — 应对多关键词 + 逐详情抓取。
        batch_index/batch_total: 分批抓取时当前批号/总批数, 用于进度显示 [批 N/M]。
        返回 { data: [ {title,url,description,published_at,meta} ], attempts, error }
        """
        payload = {
            "url": url,
            "max_attempts": 8,
            "max_pages": max_pages,
            "scrape_detail": True,
            "page_size": 10,
        }
        if query_config:
            payload.update(query_config)
        if search_keywords:
            payload["search_keywords"] = search_keywords
        if task_id:
            payload["task_id"] = task_id
        if batch_index is not None:
            payload["batch_index"] = batch_index
        if batch_total is not None:
            payload["batch_total"] = batch_total
        return self._post("/query-crawl", payload, timeout=timeout)

    def query_crawl_batched(self, url: str, query_config: Optional[dict] = None,
                            max_pages: int = 3, search_keywords: Optional[str] = "",
                            batch_size: int = 1, timeout_per_batch: float = 900.0,
                            task_id: Optional[str] = None) -> dict:
        """分批查询式抓取: 把 search_keywords 按 batch_size 拆分, 逐批调 query_crawl
        并合并去重(同 url 只保留第一条)。

        解决: 多关键词(7+) 一次性传会导致单次 httpx 耗时过长(逐条详情页抓取),
        且一处验证码失败导致全部失败。分批后单次请求稳定, 失败也只丢一批。

        返回 { data: 合并去重后的列表, attempts: 实际调用批次数, batches: 各批结果 }
        """
        # 拆分关键词(空=不传 search_keywords, 单次全量抓取)
        kws = [k.strip() for k in (search_keywords or "").split(",") if k.strip()]
        if not kws:
            r = self.query_crawl(url, query_config=query_config, max_pages=max_pages,
                                 task_id=task_id, timeout=timeout_per_batch)
            return {"data": r.get("data") or [], "attempts": 1, "batches": [r]}

        # 拆批(每批 batch_size 个关键词, 默认 1)
        batches = [kws[i:i + batch_size] for i in range(0, len(kws), batch_size)]
        merged: list = []
        seen_urls: set = set()
        batch_results: list = []
        for i, bk in enumerate(batches, 1):
            kw_str = ",".join(bk)
            try:
                r = self.query_crawl(url, query_config=query_config, max_pages=max_pages,
                                     search_keywords=kw_str,
                                     task_id=f"{task_id}-b{i}" if task_id else None,
                                     timeout=timeout_per_batch,
                                     batch_index=i, batch_total=len(batches))
                batch_results.append({"batch": i, "keywords": bk, "ok": True, "count": len(r.get("data") or [])})
            except Exception as e:  # noqa: BLE001
                logger.warning("[crawl4ai] 分批 %s 关键词 %s 失败: %s", i, bk, e)
                batch_results.append({"batch": i, "keywords": bk, "ok": False, "error": str(e)[:200]})
                continue
            for it in (r.get("data") or []):
                u = it.get("url") or it.get("link") or ""
                if not u or u in seen_urls:
                    continue
                seen_urls.add(u)
                merged.append(it)
        return {"data": merged, "attempts": len(batches), "batches": batch_results}


# 全局单例
crawl4ai_client = Crawl4aiClient()
