"""Crawl4AI 精简 HTTP 服务 — 供 SSM 后端(Python 3.9)通过 HTTP 调用爬取。

设计目标:
  - 用 Python >=3.10 环境(如 graphene 3.11)直接 import crawl4ai 库
  - 只暴露本业务需要的端点, 接口返回与之前 firecrawl 客户端兼容:
      POST /scrape  -> { url, title, markdown, published_at }
      POST /crawl   -> { data: [ {url, title, markdown, published_at, meta} ] }
      POST /query-crawl -> 查询式抓取(验证码 OCR + 模拟查询, 见 QueryCrawlRequest)
  - 整站抓取用 crawl4ai 的 BFSDeepCrawlStrategy

启动(在安装好 crawl4ai 的 3.10+ 环境):
  D:\anaconda\\envs\\graphenv\\python.exe crawl4ai_server.py
"""
import asyncio
import json
import logging
import re
import threading
import time
from typing import Optional

import ddddocr
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from playwright.async_api import async_playwright

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy

logger = logging.getLogger("crawl4ai_server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="Crawl4AI Lite Server", version="1.0.0")

_browser_config = BrowserConfig(
    headless=True,
    text_mode=True,
    extra_args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
)


class ScrapeRequest(BaseModel):
    url: str = Field(..., description="要抓取的页面 URL")
    max_depth: int = Field(1, ge=0, le=10, description="保留参数, 单页抓取固定为 1")
    wait_for: Optional[str] = Field(None, description="CSS 选择器, 等待元素出现(可选)")


class CrawlRequest(BaseModel):
    url: str = Field(..., description="种子 URL(列表页/首页)")
    max_depth: int = Field(1, ge=0, le=5, description="BFS 爬取深度(首页之外)")
    max_pages: int = Field(50, ge=1, le=500, description="最多抓取页数")
    include_urls: Optional[str] = Field(None, description="逗号分隔的 URL 关键词, 仅抓取包含任一关键词的链接(可选)")


class QueryCrawlRequest(BaseModel):
    """查询式抓取: 针对 JS 渲染 + 图形验证码的公告列表站点(如 ccgp-sichuan)。

    流程: 打开页面 -> OCR 识别验证码 -> 填表(可选条件) -> 点查询按钮
          -> 等待公告列表接口返回 -> 解析 JSON/表格 -> 逐条抓详情。
    返回 {data:[{title,url,description,published_at,meta}]}
    """
    url: str = Field(..., description="查询页 URL")
    captcha_placeholder: str = Field("验证码", description="验证码输入框 placeholder 包含的关键字")
    query_button_text: str = Field("查询", description="查询按钮文本(精确匹配)")
    captcha_img_keyword: str = Field("getVerify", description="验证码图片 src 包含的关键字")
    captcha_refresh_keyword: Optional[str] = Field("换一张", description="验证码刷新元素文本(可选)")
    api_url_keyword: str = Field("selectInfoForIndex", description="公告列表接口 URL 包含的关键字")
    result_rows_jsonpath: Optional[str] = Field("data.rows", description="公告列表 JSON 取值路径, 点分隔(如 data.rows)")
    max_attempts: int = Field(8, ge=1, le=20, description="验证码 OCR 最大重试次数")
    max_pages: int = Field(3, ge=1, le=20, description="最多翻页抓取页数")
    scrape_detail: bool = Field(True, description="是否抓取公告详情页正文")
    page_size: int = Field(10, ge=1, le=50, description="每页条数(与站点默认一致)")
    detail_url_template: Optional[str] = Field(
        None, description="详情页 URL 模板, {id} 替换公告 id / {noticeId} 替换公告 noticeId。如 https://www.ccgp-sichuan.gov.cn/maincms-web/notice/detail?id={noticeId}"
    )
    detail_id_field: Optional[str] = Field(None, description="详情 URL 用的 id 字段名, 默认自动: 有 noticeId 用 noticeId, 否则用 id")
    detail_content_selector: Optional[str] = Field(None, description="详情页正文 CSS 选择器(可选, 默认取整页文本)")
    search_keywords: Optional[str] = Field(None, description="搜索关键词, 逗号分隔。非空时在查询页的「标题」搜索框逐个填入检索(如 生态修复,地质), 结果合并去重")
    search_input_placeholder: Optional[str] = Field("标题", description="搜索输入框 placeholder 包含的关键字, 默认「标题」")
    purchaser_placeholder: Optional[str] = Field(None, description="采购人搜索框 placeholder 包含的关键字(如「采购人」)。指定后关键词填入采购人框而非标题框, 用于按单位名精准检索公告")
    channel_tab: Optional[str] = Field(None, description="查询前先点击的分类 tab 文本(如「中标（成交）公告»), 用于切换公告类型栏目后查询")
    task_id: Optional[str] = Field(None, description="任务 ID(可选), 用于通过 /query-progress/{task_id} 查询实时进度")
    batch_index: Optional[int] = Field(None, description="分批抓取的当前批号(从 1 开始, 可选, 用于进度展示 [批 N/M])")
    batch_total: Optional[int] = Field(None, description="分批抓取的总批数(可选, 用于进度展示 [批 N/M])")


def _markdown_text(result) -> str:
    """从 CrawlResult 提取正文 Markdown(优先 fit, 回退 raw)。"""
    md = getattr(result, "markdown", None)
    if md is None:
        return ""
    fit = getattr(md, "fit_markdown", None)
    if fit:
        return fit
    raw = getattr(md, "raw_markdown", None)
    return raw or ""


def _page_dict(result, url: str) -> dict:
    """CrawlResult -> {url,title,markdown,published_at,meta} 与 firecrawl 客户端兼容。"""
    meta = getattr(result, "metadata", None) or {}
    title = (
        (meta.get("title") or "")
        or getattr(result, "title", "")
        or url
    )[:512]
    return {
        "url": url,
        "title": title,
        "markdown": _markdown_text(result),
        "published_at": meta.get("date") or meta.get("publishDate"),
        "meta": meta,
    }


def _base_run_config(**overrides) -> CrawlerRunConfig:
    """基础抓取配置: 等待 JS 渲染完成(SPA 站点关键), 可覆盖。"""
    config = CrawlerRunConfig(
        scraping_strategy=LXMLWebScrapingStrategy(),
        cache_mode=CacheMode.BYPASS,
        page_timeout=60000,
        wait_until="networkidle",
        delay_before_return_html=3.0,
    )
    for k, v in overrides.items():
        setattr(config, k, v)
    return config


@app.post("/scrape")
async def scrape(req: ScrapeRequest):
    """单页抓取, 返回 {url,title,markdown,published_at}。"""
    config = _base_run_config()
    if req.wait_for:
        config.wait_for = req.wait_for
    try:
        async with AsyncWebCrawler(config=_browser_config) as crawler:
            result = await crawler.arun(url=req.url, config=config)
    except Exception as e:  # noqa: BLE001
        logger.error("scrape %s error: %s", req.url, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"crawl4ai scrape error: {e}") from e

    if not result.success:
        raise HTTPException(status_code=502, detail=result.error_message or "scrape failed")
    return _page_dict(result, req.url)


@app.post("/crawl")
async def crawl(req: CrawlRequest):
    """整站 BFS 抓取, 返回 {data:[{url,title,markdown,published_at,meta}]}。"""
    url_keywords = [k.strip() for k in (req.include_urls or "").split(",") if k and k.strip()]
    deep_strategy = BFSDeepCrawlStrategy(
        max_depth=req.max_depth,
        include_external=False,
        max_pages=req.max_pages,
    )

    config = _base_run_config(deep_crawl_strategy=deep_strategy)
    try:
        async with AsyncWebCrawler(config=_browser_config) as crawler:
            results = await crawler.arun(url=req.url, config=config)
    except Exception as e:  # noqa: BLE001
        logger.error("crawl %s error: %s", req.url, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"crawl4ai crawl error: {e}") from e

    if isinstance(results, list):
        results = list(results)
    else:
        # 0.9.2 单结果对象或异步生成器: 收集为列表
        results = [r async for r in results] if hasattr(results, "__aiter__") else [results]

    data = []
    for r in results:
        page_url = getattr(r, "url", "") or ""
        if not page_url or not getattr(r, "success", False):
            continue
        if url_keywords and not any(k.lower() in page_url.lower() for k in url_keywords):
            continue
        data.append(_page_dict(r, page_url))
    return {"data": data}


_ocr = ddddocr.DdddOcr(show_ad=False)

# ---------- 查询式抓取进度(供后端轮询透出实时日志) ----------
_query_progress: dict = {}
_query_progress_lock = threading.Lock()


def _set_progress(task_id: Optional[str], stage: str, detail: str = "") -> None:
    """记录查询式抓取阶段进度(内存, 供 /query-progress 查询)。"""
    if not task_id:
        return
    with _query_progress_lock:
        _query_progress[task_id] = {
            "stage": stage,
            "detail": detail,
            "ts": time.strftime("%H:%M:%S"),
        }


@app.get("/query-progress/{task_id}")
async def get_query_progress(task_id: str):
    """查询查询式抓取的实时进度(由后端轮询, 透出到抓取日志)。"""
    with _query_progress_lock:
        prog = dict(_query_progress.get(task_id) or {})
    return prog


def _decode_bytes(raw: bytes) -> str:
    """智能解码接口字节流: 优先 GB18030(中文政府站点常见), 回退 UTF-8。

    用"能严格解码 + 中文可读字符最多"启发式判定, 避免 GBK 字节流
    被误当作 UTF-8 解码成乱码(部分 GBK 字节序列恰好合法 UTF-8)。
    """
    if not raw:
        return ""
    candidates = []
    for enc in ("utf-8", "gb18030", "gbk"):
        try:
            s = raw.decode(enc)
            candidates.append((enc, s, _cn_ratio(s)))
        except (UnicodeDecodeError, LookupError):
            continue
    if not candidates:
        return raw.decode("utf-8", errors="replace")
    # 选中文可读字符占比最高者
    best = max(candidates, key=lambda c: c[2])
    # 无中文时选第一个能解码的
    if best[2] <= 0:
        return candidates[0][1]
    return best[1]


def _cn_ratio(s: str) -> float:
    """中文字符占可打印字符比例。"""
    total = 0
    cn = 0
    for ch in s:
        if "\u4e00" <= ch <= "\u9fff":
            cn += 1
            total += 1
        elif ch.isprintable() and not ch.isspace():
            total += 1
    return cn / total if total else 0.0


def _get_json_path(obj, path: str):
    """按点分隔路径取值, 如 data.rows; 任意段缺失返回 None。"""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if cur is None:
            return None
    return cur


async def _refresh_captcha(page, req: QueryCrawlRequest) -> None:
    """刷新验证码: 优先点"换一张", 否则点验证码图片。"""
    try:
        el = page.get_by_text(req.captcha_refresh_keyword or "__none__", exact=False).first
        if await el.count() > 0:
            await el.click(timeout=3000)
            return
    except Exception:  # noqa: BLE001
        pass
    try:
        imgs = await page.query_selector_all("img")
        for img in imgs:
            src = await img.get_attribute("src") or ""
            if req.captcha_img_keyword in src:
                await img.click(timeout=3000)
                return
    except Exception:  # noqa: BLE001
        pass


async def _get_captcha_img(page, req: QueryCrawlRequest) -> bytes:
    """从验证码 img 元素获取图片字节。"""
    imgs = await page.query_selector_all("img")
    for img in imgs:
        src = await img.get_attribute("src") or ""
        if req.captcha_img_keyword in src:
            full = src if src.startswith("http") else f"https://{req.url.split('/')[2]}{src}"
            try:
                resp = await page.request.get(full)
                return await resp.body()
            except Exception:  # noqa: BLE001
                return b""
    return b""


async def _find_input_by_placeholder(page, keyword: str):
    """按 placeholder 包含关键字找输入框。"""
    for inp in await page.query_selector_all("input"):
        ph = (await inp.get_attribute("placeholder") or "")
        if keyword and keyword in ph:
            return inp
    return None


async def _query_crawl_page(page, req: QueryCrawlRequest, search_keyword: Optional[str] = None) -> dict:
    """在已打开的页面上: OCR 验证码 -> 填表(可选搜索词) -> 点查询 -> 抓公告列表。返回 {rows, err}"""
    captcha_input = await _find_input_by_placeholder(page, req.captcha_placeholder)
    if not captcha_input:
        return {"rows": [], "err": f"未找到验证码输入框(placeholder 含 {req.captcha_placeholder})"}

    # 搜索输入框(可选): 指定采购人框则按采购人检索, 否则用标题/自定义框
    search_input = None
    if search_keyword:
        if req.purchaser_placeholder:
            search_input = await _find_input_by_placeholder(page, req.purchaser_placeholder)
            if search_input is None:
                # 采购人框未找到, 回退标题框并记录
                search_input = await _find_input_by_placeholder(page, req.search_input_placeholder or "标题")
        else:
            search_input = await _find_input_by_placeholder(page, req.search_input_placeholder or "标题")

    # 分类 tab(可选): 切换公告类型栏目再查询。
    if req.channel_tab:
        try:
            # 等待 Vue 组件就绪(dictList 异步加载), 最多 10s
            injected = "no_vue"
            for _ in range(20):
                injected = await page.evaluate("""(tabName) => {
                  const root = document.querySelector('#app') || document.querySelector('#main-app');
                  function find(v, depth) {
                    if (!v || depth > 8) return null;
                    const p = v.$data;
                    if (p && p.params && p.params.noticeType !== undefined) return v;
                    const ch = v.$children;
                    if (ch) { for (const c of ch) { const r = find(c, depth + 1); if (r) return r; } }
                    return null;
                  }
                  const comp = root && root.__vue__ ? find(root.__vue__, 0) : null;
                  if (!comp || !comp.$data || !comp.$data.dictList) return "no_vue";
                  const item = (comp.$data.dictList || []).find(d => d.dictName === tabName);
                  if (!item) return "no_tab:" + tabName;
                  if (typeof comp.changeChannel === "function") { comp.changeChannel(item); return "changeChannel:" + item.dictCode; }
                  comp.$data.params.noticeType = item.dictCode;
                  comp.$data.dictTagActive = item.id;
                  return "fallback:" + item.dictCode;
                }""", req.channel_tab)
                if not injected.startswith("no_vue"):
                    break
                await page.wait_for_timeout(500)
            await page.wait_for_timeout(1500)
            if injected.startswith("no_tab") or injected == "no_vue":
                _set_progress(req.task_id, "切换栏目", f"注入失败({injected}), 回退点击")
                # 回退: 点击含 tab 文本的可点击元素
                tab_btn = page.get_by_text(req.channel_tab, exact=False).first
                if await tab_btn.count() > 0:
                    await tab_btn.click(timeout=5000)
                    await page.wait_for_timeout(1500)
            else:
                _set_progress(req.task_id, "切换栏目", f"注入成功: {injected}")
        except Exception:  # noqa: BLE001
            pass

    api_bodies = []

    async def _on_response(resp):
        if req.api_url_keyword in resp.url:
            try:
                if "json" in resp.headers.get("content-type", ""):
                    raw = await resp.body()
                    api_bodies.append(_decode_bytes(raw))
            except Exception:  # noqa: BLE001
                pass

    page.on("response", _on_response)

    rows = []
    last_err = ""
    for attempt in range(req.max_attempts):
        img_bytes = await _get_captcha_img(page, req)
        if not img_bytes:
            last_err = "未获取到验证码图片"
            break
        code = _ocr.classification(img_bytes)
        if len(code) < 2:
            await _refresh_captcha(page, req)
            await asyncio.sleep(1.0)
            continue
        try:
            await captcha_input.fill(code)
        except Exception as e:  # noqa: BLE001
            last_err = f"填验证码失败: {e}"
            break
        # 填搜索关键词(可选)
        if search_input is not None:
            try:
                await search_input.fill(search_keyword or "")
            except Exception:  # noqa: BLE001
                pass
        try:
            btn = page.get_by_text(req.query_button_text, exact=True).first
            await btn.click(timeout=5000)
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(4.0)
        if api_bodies:
            body = api_bodies[-1]
            try:
                parsed = json.loads(body)
            except Exception:  # noqa: BLE001
                last_err = "接口响应非 JSON"
                await _refresh_captcha(page, req)
                await asyncio.sleep(1.0)
                continue
            if parsed.get("code") in ("200", 200, "0", 0, "success"):
                rows = _get_json_path(parsed, req.result_rows_jsonpath or "data.rows") or []
                if not isinstance(rows, list):
                    rows = [rows] if rows else []
                return {"rows": rows, "err": ""}
            last_err = f"接口返回 code={parsed.get('code')}"
            await _refresh_captcha(page, req)
            await asyncio.sleep(1.0)
        else:
            last_err = "未捕获到公告列表接口响应"
            await _refresh_captcha(page, req)
            await asyncio.sleep(1.0)
    return {"rows": [], "err": last_err or "验证码识别重试次数用尽"}


def _build_detail_url(row: dict, page_url: str, req: QueryCrawlRequest) -> str:
    """生成公告详情页真实 URL。

    优先级: 接口返回的 noticeDetailUrl/url > 模板拼接 > 默认 article 规则。
    注意: ccgp-sichuan 详情页是 /maincms-web/article?type=notice&id={id}&planId={planId},
    其中 id 是列表行 id(UUID), planId 是采购计划 id; 直接用该 URL 渲染即显示对应公告。
    """
    detail_url = row.get("noticeDetailUrl") or row.get("url") or ""
    if detail_url:
        if not detail_url.startswith("http"):
            host = page_url.split("/")[2]
            detail_url = f"https://{host}{detail_url}"
        return detail_url

    host = page_url.split("/")[2]
    if req.detail_url_template:
        tpl = req.detail_url_template
        tpl = tpl.replace("{noticeId}", str(row.get("noticeId") or ""))
        tpl = tpl.replace("{id}", str(row.get("id") or ""))
        tpl = tpl.replace("{planId}", str(row.get("planId") or ""))
        return tpl
    # 默认 article 规则(ccgp-sichuan 已验证直接访问可渲染对应公告)
    row_id = row.get("id") or row.get("noticeId") or ""
    plan_id = row.get("planId") or ""
    if row_id:
        return f"https://{host}/maincms-web/article?type=notice&id={row_id}&planId={plan_id}"
    return ""


def _parse_announce_times(row: dict) -> dict:
    """从公告行提取时间字段(供后端按时间窗口过滤 + 结构化展示)。

    注意: 该站接口的 openTenderTime 与 expireTime 相同(非真实开标时间),
    故不生成 open_tender_time 误导展示。只保留可靠的:
      expire_time 截止时间 / notice_time 发布时间
    """
    def _norm(v):
        if v in (None, "", "null"):
            return None
        return str(v)

    start = _norm(row.get("starttime") or row.get("startTime"))
    end = _norm(row.get("endtime") or row.get("endTime") or row.get("noticeEndTime"))
    expire = _norm(row.get("expireTime"))
    return {
        "start_time": start,
        "end_time": end,
        "expire_time": expire,
    }


def _notice_dict(row: dict, page_url: str, req: QueryCrawlRequest) -> dict:
    """公告行 JSON -> 通用字段(保留结构化字段: 标题/正文/详情URL/时间/预算/采购人/代理)。"""
    detail_url = _build_detail_url(row, page_url, req)
    times = _parse_announce_times(row)
    # 保留全部原始字段, 供后端结构化展示
    meta = {k: v for k, v in row.items() if v not in (None, "", "null")}
    meta.update({k: v for k, v in times.items() if v})
    return {
        "title": (row.get("title") or row.get("noticeName") or row.get("name") or "")[:512],
        "url": detail_url,
        "description": (row.get("description") or row.get("summary") or row.get("content") or "")[:8000],
        "published_at": row.get("noticeTime") or row.get("publishTime") or row.get("addtime") or row.get("date"),
        "meta": meta,
    }


def _clean_article_text(text: str) -> str:
    """清理 article 页正文: 去掉头部导航/公告信息头/尾部页脚, 只保留公告正文。

    正文从「项目概况」或标题行开始, 到「相关附件」/「附件」或「免责声明」附近结束。
    """
    if not text:
        return ""
    # 找正文起点: 优先「项目概况」, 其次公告标题
    start = text.find("项目概况")
    if start < 0:
        # 尝试找标题行(带【信息发布主体】的)
        for line in text.split("\n"):
            if "信息发布主体" in line:
                start = text.find(line)
                break
    if start < 0:
        start = 0
    # 找正文终点: 相关附件/免责声明
    end = len(text)
    for tail in ["相关附件", "免责声明", "附件：", "附件:"]:
        t = text.find(tail, start)
        if 0 < t < end:
            end = t
    body = text[start:end]
    # 去掉开头可能的「项目概况」重复或标题行
    lines = [ln.strip() for ln in body.split("\n")]
    # 去掉空行压缩
    cleaned = "\n".join(ln for ln in lines if ln)
    return cleaned[:30000]


_INVALID_CONTACT_NAMES = ("交易组织", "综合股", "办公室", "财务室", "综合科", "项目办",
                          "招标代理", "代理机构", "采购人代表", "经办人", "单位", "机构",
                          "部门", "负责人", "联系人", "交易中心", "工作人员")


def _valid_person_name(name: str) -> bool:
    """联系人姓名合法性: 2-4 汉字且非电话/角色/科室词。"""
    import re as _r
    if not name or not isinstance(name, str):
        return False
    n = name.strip()
    if not _r.fullmatch(r"[\u4e00-\u9fa5·]{2,4}", n):
        return False
    if any(k in n for k in _INVALID_CONTACT_NAMES):
        return False
    if _r.search(r"[0-9()（）\-]", n):
        return False
    return True


def _parse_contact_sections(text: str) -> dict:
    """从公告正文「凡对本次公告内容提出询问」段解析 采购人/代理机构/项目联系人。

    支持两种格式:
      「1.采购人信息 / 2.采购代理机构信息 / 3.项目联系方式」(ccgp-sichuan)
      「采购人:... / 代理机构:... / 项目联系人:... / 项目联系电话:...」(ccgp 通用)
    鲁棒性(不依赖特定版式):
      - 无「凡对本次公告…」头也能解析(直接扫全文小节锚点)
      - 联系方式段后跟着 落款公司名/日期/其他内容 不受影响(正则精确匹配目标行)
      - 缺某小节(如无项目联系方式)则返回空 dict, 不误抓其他字段
    返回 {purchaser:{name,addr,contact,phone}, agency:{...}, project:{contact,phone}}
    """
    empty = {"purchaser": {}, "agency": {}, "project": {}}
    if not text:
        return empty
    # 定位「联系」段起点; 找不到头也不放弃, 直接全文扫锚点
    tail = None
    for marker in ("凡对本次公告内容提出询问", "按以下方式联系"):
        idx = text.find(marker)
        if idx >= 0:
            tail = text[idx:]
            break
    if tail is None:
        tail = text
    # 裁到「附件/相关附件」之前
    for tail_kw in ("相关附件", "附件：", "附件:"):
        t = tail.find(tail_kw)
        if t > 0:
            tail = tail[:t]
    # 按小节切分
    import re as _r
    sections = {}
    for m in _r.finditer(r"(\d\.|（\d）)?\s*(采购人信息|采购代理机构信息|代理机构信息|项目联系方式|采购人|采购代理机构|项目联系人|采购人名称|代理机构名称)", tail):
        key = (m.group(2) or "").strip()
        if "采购人" in key:
            sections.setdefault("purchaser", m.start())
        elif "代理" in key:
            sections.setdefault("agency", m.start())
        elif key in ("项目联系方式", "项目联系人"):
            sections.setdefault("project", m.start())
    if not sections:
        return empty
    ordered = sorted(sections.items(), key=lambda x: x[1])
    result = empty
    for i, (key, pos) in enumerate(ordered):
        end = ordered[i + 1][1] if i + 1 < len(ordered) else len(tail)
        seg = tail[pos:end]
        if key == "project":
            name = ""
            m = _r.search(r"项目联系人[：:\s]*([\u4e00-\u9fa5·]{2,4})", seg)
            if m:
                name = m.group(1)
            elif not name:
                m0 = _r.search(r"(?:联系人|采购人代表)[：:\s]*([\u4e00-\u9fa5·]{2,4})", seg)
                if m0:
                    name = m0.group(1)
            # 注意: 不能用「联系?电话」—— 联系? 匹配「联系」或「联」(不能为空), 电话前无「联」就失败。
            # 用 (?:联系)?电话 匹配「联系电话」或「电话」
            m2 = _r.search(r"(?:项目)?(?:联系)?电话[：:\s]*([0-9\-()（）\s]{6,20})", seg)
            if name and not _valid_person_name(name):
                name = ""   # 电话/角色/科室误判为姓名 → 置空
            result["project"] = {"contact": name, "phone": m2.group(1).strip() if m2 else ""}
            continue
        d = {}
        m = _r.search(r"名称[：:\s]*([^\n]{2,60})", seg)
        if m:
            d["name"] = m.group(1).strip()
        m = _r.search(r"地址[：:\s]*([^\n]{2,80})", seg)
        if m:
            d["addr"] = m.group(1).strip()
        m = _r.search(r"联系方式?[：:\s]*([^\n]{2,40})", seg)
        if m:
            d["contact"] = m.group(1).strip()
        elif not d.get("contact"):
            m1 = _r.search(r"联系人[：:\s]*([\u4e00-\u9fa5·]{2,4})", seg)
            if m1:
                d["contact"] = m1.group(1).strip()
        # 电话: 独立行优先; 无则从「联系方式」值中提取(如 张先生 (028) 8486 3251)
        m = _r.search(r"([0-9\-()（）\s]{6,20})", seg.split("名称")[0])
        if m:
            d["phone"] = m.group(1).strip()
        elif d.get("contact"):
            m2 = _r.search(r"([0-9][0-9\-()（）\s]{5,19})", d["contact"])
            if m2:
                d["phone"] = m2.group(1).strip()
        # 电话清洗: 去掉残留的全角/半角右括号「)」（如 (028) 8486 3251 → 028-8486-3251）
        if d.get("phone"):
            p = _r.sub(r"[)）]", "", d["phone"]).strip()
            p = _r.sub(r"\s*-\s*", "-", p)
            p = _r.sub(r"\s+", "-", p)
            d["phone"] = p
        result[key] = d
    return result


async def _extract_attachments(page) -> list:
    """从 article 详情页提取「相关附件」区的附件链接(文件名+下载URL)。

    附件是 <a> 链接, 文件名如「若尔盖县…(采购需求).pdf」,
    下载地址形如 https://gpx.ccgp-sichuan.gov.cn/gpx-public-file?accessCode=...
    """
    try:
        links = await page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({t: e.innerText.trim(), h: e.getAttribute('href')})).filter(x => x.t && x.t.length > 1)"
        )
    except Exception:  # noqa: BLE001
        return []
    # 过滤附件区链接: 排除导航/按钮(短文本、gpx 域名之外的收藏/打印/关闭等)
    result = []
    skip_txt = {"打印", "关闭", "收藏", "大", "中", "小", "首页", "返回"}
    for l in links:
        t = (l.get("t") or "").strip()
        h = (l.get("h") or "").strip()
        if not t or not h or t in skip_txt or len(t) < 3:
            continue
        # 附件链接特征: 文件名含扩展名(.pdf/.doc/.xls/.zip) 或 gpx 下载域名
        is_file = any(t.lower().endswith(ext) for ext in
                      (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar", ".7z", ".jpg", ".png"))
        is_gpx = "gpx" in h.lower() or "file" in h.lower() or "attach" in h.lower()
        if not is_file and not is_gpx:
            continue
        result.append({"name": t, "url": h})
    return result


async def _fetch_detail_text(detail_url: str) -> tuple:
    """抓取公告详情页(article 页)完整正文 + 附件列表。

    返回 (正文文本, [ {name,url} ])。失败返回 ("", [])。
    加强: 等 JS 渲染出正文(轮询 body 文本增长, 最多 ~20s), 失败自动重试一次
    (修复: 原固定 6s 等待, SPA 偶发渲染慢 → detail_text 为空 → 项目概况退化为摘要)。
    """
    if not detail_url:
        return "", []

    async def _one_attempt() -> tuple:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0")
                await page.goto(detail_url, wait_until="load", timeout=45000)
                # 轮询等待正文渲染: SPA 页面正文通常 >300 字符
                text = ""
                for _ in range(20):
                    await page.wait_for_timeout(1000)
                    text = str(await page.evaluate("document.body ? document.body.innerText : ''"))
                    if len(text) > 300 and ("项目" in text or "采购" in text):
                        break
                attachments = await _extract_attachments(page)
                return _clean_article_text(text), attachments
            finally:
                await browser.close()

    try:
        cleaned, attachments = await _one_attempt()
        # 正文过短/为空 → 重试一次
        if len(cleaned) < 200:
            cleaned, attachments = await _one_attempt()
        return cleaned, attachments
    except Exception as e:  # noqa: BLE001
        logger.warning("detail fetch %s error: %s", detail_url, e)
        return "", []


def _clean_section(s: str) -> str:
    """清理段落: 去掉开头冒号/空白/换行, 压缩空行。"""
    if not s:
        return ""
    s = s.lstrip("：: \n\t")
    lines = [ln.strip() for ln in s.split("\n")]
    return "\n".join(ln for ln in lines if ln).strip()[:4000]


def _parse_article_sections(text: str) -> dict:
    """从公告详情正文解析结构化段落(项目概况/资格要求/资质等)。

    返回 {overview, qualification, specific_qualification, full_text}
    """
    if not text:
        return {"overview": "", "qualification": "", "specific_qualification": "", "full_text": ""}

    def _section(keyword: str) -> str:
        idx = text.find(keyword)
        if idx < 0:
            return ""
        # 从关键词后找正文起点(跳过冒号)
        rest = text[idx + len(keyword):]
        # 找下一个一级标题(一、二、三… 或 附件/免责声明)
        for m in re.finditer(r"\n\s*([一二三四五六七八九十]+、)", rest):
            return _clean_section(rest[:m.start()])
        for tail in ["相关附件", "免责声明"]:
            t_idx = rest.find(tail)
            if t_idx >= 0:
                return _clean_section(rest[:t_idx])
        return _clean_section(rest)

    overview = _section("项目概况")
    # 项目概况关键词可能命中导航区, 用「一、项目基本情况」更准确
    if not overview or len(overview) < 20:
        overview = _section("一、项目基本情况")
    qualification = _section("资格要求")
    specific = _section("特定资格要求")
    # qualification 里可能含特定资格, 若 specific 空则从 qualification 提取
    if not specific and qualification:
        idx = qualification.find("特定资格要求")
        if idx >= 0:
            specific = _clean_section(qualification[idx:])
            qualification = _clean_section(qualification[:idx])
    return {
        "overview": overview,
        "qualification": qualification,
        "specific_qualification": specific,
        "full_text": text,
    }


def _parse_procurement_result(text: str) -> list:
    """从中标(成交)结果公告正文解析「三、采购结果」表格。

    表格为 markdown pipe 格式:
      | 供应商名称  | 供应商地址  | 中标（成交）金额  | 评审总得分  |
      | --- | --- | --- | --- |
      | 四川长巨科技有限公司  | 成都高新区府城大道西段399号...  |  669,500.00元  | 98.93  |
    同一项目可有多个采购包(采购包1/采购包2…), 每个含独立表格行。

    返回 [ {supplier, address, amount} ] (去空行, 名称纯数字/表头行丢弃)。
    """
    if not text:
        return []
    # 定位「三、采购结果」段(或「中标(成交)供应商」文本), 到下一个一级标题前
    start = text.find("三、采购结果")
    if start < 0:
        start = text.find("中标（成交）供应商")
        if start < 0:
            start = text.find("四、主要标的信息")
    if start < 0:
        return []
    end = len(text)
    for kw in ("四、主要标的信息", "五、评审专家", "五、评审"):
        i = text.find(kw, start + 10)
        if 0 < i < end:
            end = i
            break
    block = text[start:end]

    result = []
    header_seen = False
    for line in block.split("\n"):
        line = line.strip()
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            row = _procurement_row(cells)
            if row is None:
                continue
            if row.get("_header"):
                header_seen = True
                continue
            if not header_seen:
                continue
            result.append(row)
            header_seen = False
        elif "\t" in line:
            # innerText 表格: tab 分隔, 首行表头含「供应商名称/供应商地址」
            cells = [c.strip() for c in line.split("\t")]
            row = _procurement_row(cells)
            if row is None:
                continue
            if row.get("_header"):
                header_seen = True
                continue
            if not header_seen:
                continue
            result.append(row)
            header_seen = False
    return result


def _procurement_row(cells: list) -> dict:
    """把一行单元格解析为 {supplier,address,amount} 或 {_header:True} 或 None(非表行)。

    跳过: 空行 / 分隔线(---) / 纯数字或数字缩写行(价格表格数据)。
    """
    if not cells:
        return None
    if any(c.strip().replace("-", "").replace("+", "") == "" for c in cells):
        return None
    cleaned = [c for c in cells if c.strip()]
    if not cleaned:
        return None
    first = cleaned[0]
    # 表头行
    if any(("供应商名称" in c or "供应商地址" in c) for c in cleaned):
        return {"_header": True}
    # 分隔线(---)行
    if all(re.fullmatch(r"[-:\s]*", c) for c in cleaned):
        return None
    if len(cleaned) < 3:
        return None
    supplier = cleaned[0]
    address = cleaned[1]
    # 金额: 优先含「元」或数字的单元格
    amount_cell = ""
    for c in cleaned[2:]:
        if "元" in c or re.search(r"\d", c):
            amount_cell = c
            break
    if not amount_cell and len(cleaned) > 3:
        amount_cell = cleaned[2]
    amount_cell = amount_cell.replace(",", "")
    if supplier and not re.fullmatch(r"[\d\s]+", supplier) and "供应商名称" not in supplier:
        return {"supplier": supplier[:120], "address": address[:200], "amount": amount_cell[:80]}
    return None


@app.post("/query-crawl")
async def query_crawl(req: QueryCrawlRequest):
    """查询式抓取: JS 渲染 + 图形验证码的公告列表站点。

    返回 {data:[{title,url,description,published_at,meta}], attempts, error}
    """
    def _bp() -> str:
        """批次进度前缀: 分批抓取时显示 [批 N/M], 否则空串。"""
        if req.batch_index and req.batch_total:
            return f"[批 {req.batch_index}/{req.batch_total}] "
        return ""

    try:
        _set_progress(req.task_id, "打开页面", f"{_bp()}加载 {req.url}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0")
            await page.goto(req.url, wait_until="load", timeout=60000)
            await page.wait_for_timeout(5000)

            all_rows = []
            seen_urls = set()
            detail_count = {"n": 0}

            async def _collect(result):
                for row in result.get("rows", []):
                    item = _notice_dict(row, req.url, req)
                    url = item.get("url") or ""
                    if url and url in seen_urls:
                        continue
                    if url:
                        seen_urls.add(url)
                    # 抓详情正文 + 结构化解析(项目概况/资格要求/资质) + 附件
                    if req.scrape_detail and url:
                        detail_count["n"] += 1
                        _set_progress(req.task_id, "抓详情",
                                      f"{_bp()}第 {detail_count['n']} 条: {(item.get('title') or '')[:22]}")
                        detail_text, attachments = await _fetch_detail_text(url)
                        if detail_text:
                            sections = _parse_article_sections(detail_text)
                            item["detail_content"] = detail_text
                            item["overview"] = sections["overview"]
                            item["qualification"] = sections["qualification"]
                            item["specific_qualification"] = sections["specific_qualification"]
                            meta = item.get("meta") or {}
                            meta["overview"] = sections["overview"]
                            meta["qualification"] = sections["qualification"]
                            meta["specific_qualification"] = sections["specific_qualification"]
                            winners = _parse_procurement_result(detail_text)
                            if winners:
                                meta["procurement_result"] = winners
                            if attachments:
                                meta["attachments"] = attachments
                            # 联系方式结构化解析(采购人/代理机构/项目联系人) → meta
                            contacts = _parse_contact_sections(detail_text)
                            if contacts.get("purchaser"):
                                meta["purchaser_contact"] = contacts["purchaser"]
                            if contacts.get("agency"):
                                meta["agency_contact"] = contacts["agency"]
                            if contacts.get("project"):
                                meta["project_contact"] = contacts["project"]
                            item["meta"] = meta
                    all_rows.append(item)

            async def _next_page() -> bool:
                """点击翻页按钮(Element Plus 分页 .btn-next 箭头或文本「下一页」)。

                返回是否成功翻页(无按钮/点击异常返回 False)。
                """
                try:
                    # 优先 Element Plus 分页的 .btn-next 箭头按钮(站点为 el-pagination)
                    next_btns = await page.query_selector_all(
                        ".el-pagination .btn-next, .btn-next, .el-pagination li.btn-next"
                    )
                    if next_btns:
                        disabled = await next_btns[0].get_attribute("disabled")
                        if disabled is None:
                            await next_btns[0].click(timeout=4000)
                            await page.wait_for_timeout(1500)
                            return True
                except Exception:  # noqa: BLE001
                    pass
                try:
                    next_btn = page.get_by_text("下一页", exact=False).first
                    if await next_btn.count() > 0:
                        await next_btn.click(timeout=4000)
                        await page.wait_for_timeout(1500)
                        return True
                except Exception:  # noqa: BLE001
                    pass
                return False

            async def _collect_paged(first_result: dict, label_prefix: str, start_page: int = 2) -> None:
                """翻页收集: 已抓完第 1 页, 从第 start_page 页点「下一页」并解析当前页数据。

                先挂接口监听, 再点击翻页(避免响应先到而监听错过), 等响应后解析 rows。
                """
                for page_idx in range(start_page, req.max_pages + 1):
                    if not first_result.get("rows"):
                        break
                    _set_progress(req.task_id, label_prefix, f"第 {page_idx} 页")
                    api_bodies = []

                    async def _on_paged(resp):
                        if req.api_url_keyword in resp.url:
                            try:
                                if "json" in resp.headers.get("content-type", ""):
                                    raw = await resp.body()
                                    api_bodies.append(_decode_bytes(raw))
                            except Exception:  # noqa: BLE001
                                pass

                    page.on("response", _on_paged)
                    if not await _next_page():
                        break
                    # 等待接口响应并解析当前页
                    for _ in range(6):
                        if api_bodies:
                            break
                        await asyncio.sleep(1.0)
                    if not api_bodies:
                        break
                    try:
                        parsed = json.loads(api_bodies[-1])
                    except Exception:  # noqa: BLE001
                        break
                    if parsed.get("code") not in ("200", 200, "0", 0, "success"):
                        break
                    rows = _get_json_path(parsed, req.result_rows_jsonpath or "data.rows") or []
                    if not isinstance(rows, list):
                        rows = [rows] if rows else []
                    if not rows:
                        break
                    await _collect({"rows": rows})

            # 搜索关键词: 逗号分隔, 逐个检索(支持翻页), 合并去重
            keywords = [k.strip() for k in (req.search_keywords or "").split(",") if k and k.strip()]
            if keywords:
                for i, kw in enumerate(keywords, 1):
                    _set_progress(req.task_id, "站内检索", f"{_bp()}关键词 {i}/{len(keywords)}: {kw}")
                    result = await _query_crawl_page(page, req, search_keyword=kw)
                    await _collect(result)
                    # 翻页: 搜索后点「下一页」, 站点会保留搜索词继续翻
                    await _collect_paged(result, f"站内检索 {kw}")
            else:
                # 无搜索词: 直接抓列表, 支持翻页
                result = await _query_crawl_page(page, req)
                await _collect(result)
                await _collect_paged(result, "抓列表")

            await browser.close()
        _set_progress(req.task_id, "完成", f"共收集 {len(all_rows)} 条")
    except Exception as e:  # noqa: BLE001
        logger.error("query-crawl %s error: %s", req.url, e, exc_info=True)
        _set_progress(req.task_id, "失败", str(e)[:120])
        raise HTTPException(status_code=500, detail=f"crawl4ai query-crawl error: {e}") from e

    return {"data": all_rows, "attempts": 1, "error": ""}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "crawl4ai-lite"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=11235)
