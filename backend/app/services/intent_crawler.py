"""意向性信息爬取服务 — 政务源(发改委/交通厅/自然资源局等)列表+详情 → 结构化 → intent_notice。

流程:
  1. 从 web_source 的 scrape_mode='intent' 来源拉列表页
  2. 提取详情链接(栏目页 common_list.shtml / index 等)
  3. 抓详情页正文, 用 LLM 抽取结构化字段(项目类型/金额/地域/部门/联系人/时间)
  4. 写入 intent_notice(幂等: 同 url 更新)
  5. 与 web_clue 线索库去重(同 url 已有 web_clue 则跳过)

说明: 政务网站多为静态可抓(无验证码), 走 requests/httpx; 若个别站点 JS 渲染
则回退 crawl4ai scrape。结构化抽取复用 knowledge_extractor 的 LLM 能力。
"""
import logging
import re
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.web_source import WebSource
from app.models.web_clue import WebClue
from app.models.intent_notice import IntentNotice
from app.services.china_regions import resolve_region, is_target_province, extract_target_province

logger = logging.getLogger("intent_crawler")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

# 详情链接模式: 政务站常见 /2026/2/12/xxx.shtml 形式
_DETAIL_URL_RE = re.compile(r'href="([^"]+/(?:20\d{2})/\d{1,2}/\d{1,2}/[^"]+\.shtml)"')
# 纯文本列表站(可选 include_urls 配置)


def _fetch(url: str, timeout: int = 15) -> Optional[str]:
    try:
        r = httpx.get(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"},
                      timeout=timeout, follow_redirects=True)
        if r.status_code == 200:
            return r.text
    except Exception as e:  # noqa: BLE001
        logger.warning("抓取失败 %s: %s", url, e)
    return None


def _extract_detail_links(html: str, base_url: str, limit: int = 20) -> list:
    """从列表页 HTML 提取详情链接(去重, 优先详情页 shtml)。"""
    seen, out = set(), []
    for m in _DETAIL_URL_RE.finditer(html):
        href = m.group(1).strip()
        if not href.startswith("http"):
            href = href if href.startswith("/") else f"/{href}"
            href = f"{base_url}{href}"
        # 清理相对路径(../)
        while "/../" in href:
            href = href.replace("/../", "/", 1)
        if href in seen:
            continue
        seen.add(href)
        out.append(href)
        if len(out) >= limit:
            break
    return out


def _extract_title(html: str) -> str:
    m = re.search(r"<title>([^<]+)</title>", html)
    return m.group(1).strip() if m else ""


def _extract_body_text(html: str) -> str:
    """粗略正文提取(政务站正文通常在 <div class='content'> 或 <p> 密集区)。"""
    # 去掉 script/style
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # 优先 content 容器
    m = re.search(r"<div[^>]*(?:class|id)=[\"'](?:content|article|TRS_Editor|view)[^\"']*[\"'][^>]*>(.*?)</div>", html, re.DOTALL | re.IGNORECASE)
    block = m.group(1) if m else html
    text = re.sub(r"<[^>]+>", "\n", block)
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()[:6000]


# 项目类型关键词(从标题/正文识别, 与 business_network 专长映射对齐)
# 注意: 数组顺序即优先级, transport(公路/铁路)这类应排最前, 避免被正文「地质灾害防治」误抢
_TYPE_KEYWORDS = [
    ("公路", "transport"), ("铁路", "transport"), ("高速", "transport"),
    ("桥梁", "transport"), ("隧道", "transport"), ("机场", "transport"), ("码头", "transport"),
    ("水电", "energy"), ("光伏", "energy"), ("风电", "energy"), ("天然气", "energy"),
    ("矿业权", "mining_rights"), ("采矿", "mining_rights"), ("矿产资源", "mining_rights"),
    ("地质灾害", "geo_hazard"), ("地灾", "geo_hazard"), ("滑坡", "geo_hazard"), ("泥石流", "geo_hazard"),
    ("地质勘察", "geo_survey"), ("地质勘查", "geo_survey"), ("工程勘察", "geo_survey"), ("岩土", "geo_survey"),
    ("生态修复", "eco_restoration"), ("环境治理", "eco_restoration"),
    ("市政", "municipal"), ("管网", "municipal"), ("供水", "municipal"), ("污水", "municipal"),
    ("水利", "water"), ("水库", "water"), ("堤防", "water"),
    ("学校", "education"), ("医院", "healthcare"),
]

_TYPE_LABELS = {
    "geo_hazard": "地质灾害治理", "geo_survey": "地质勘察", "eco_restoration": "生态修复",
    "mining_rights": "矿业权", "transport": "交通工程", "energy": "能源工程",
    "municipal": "市政工程", "water": "水利工程", "education": "教育设施", "healthcare": "医疗设施",
}

_AMOUNT_RE = re.compile(r"(?:总投资|投资|估算|预算)[约\s]*([\d,，.]+)\s*(?:亿|万元?)")
_AMOUNT_UNIT = {"亿": 10000, "万": 1, "万元": 1}


def _parse_amount(text: str) -> Optional[float]:
    """从正文提取金额(万元)。支持 亿/万。

    会议/调度/座谈等非批复类新闻的「2026年度」「3400人次」等数字不算金额,
    需金额关键词(总投资/投资/估算/预算)紧邻数字。
    """
    if any(k in text for k in ("会议", "调度", "座谈", "专题会", "调研", "培训")):
        return None
    for m in _AMOUNT_RE.finditer(text):
        num = float(m.group(1).replace(",", "").replace("，", ""))
        unit = "万" if "亿" not in m.group(0) else "亿"
        return round(num * (10000 if unit == "亿" else 1), 2)
    return None


def _parse_type(title: str, body: str = "") -> tuple:
    """识别项目类型。优先标题(标题通常直接含项目类型词), 正文补充。

    返回 (type_key, label)。两者都未命中返回 ("", "")。
    """
    for kw, key in _TYPE_KEYWORDS:
        if kw in title:
            return key, _TYPE_LABELS.get(key, key)
    for kw, key in _TYPE_KEYWORDS:
        if kw in body:
            return key, _TYPE_LABELS.get(key, key)
    return "", ""


def _parse_contact(text: str) -> str:
    """提取联系人/电话。"""
    m = re.search(r"(?:联系人|联系电话|联系单位)[：:]\s*([^\n]{2,60})", text)
    if m:
        return m.group(1).strip()[:200]
    return ""


def _parse_dept(html: str, text: str) -> str:
    m = re.search(r"<meta name=\"ContentSource\" content=\"([^\"]+)\"", html)
    if m:
        return m.group(1).strip()
    m = re.search(r"发文机关[：:]\s*([^\n<]{2,40})", text)
    if m:
        return m.group(1).strip()
    return ""


# 常见四川市县关键词(标题/正文匹配, 用于地域识别)
_REGION_WORDS = [
    "成都", "自贡", "攀枝花", "泸州", "德阳", "绵阳", "广元", "遂宁", "内江", "乐山",
    "南充", "眉山", "宜宾", "广安", "达州", "雅安", "巴中", "资阳",
    "汉源县", "普兰县", "定日县", "喜德县", "雷波县", "青川县", "北川县", "白玉县",
    "石渠县", "色达县", "茂县", "马边县", "南江县", "三台县", "中江县", "古蔺县",
    "叙永县", "筠连县", "合江县", "隆昌", "荣县", "威远县", "剑阁县", "旺苍县",
    "峨眉山", "西昌", "康定", "马尔康", "江油", "阆中", "万源", "华蓥",
    "凉山", "阿坝", "甘孜", "泸州", "宜宾", "资阳", "达州", "巴中", "遂宁", "内江", "德阳", "广元", "雅安", "南充", "乐山", "攀枝花", "自贡", "广安", "绵阳", "眉山",
]

# 目标省份(川藏新)全部市级+县级词, 供 _region_of 自动识别
# 从 china_regions 动态生成, 避免手写遗漏
from app.services.china_regions import REGION_COUNTIES, _CITY_OF, TARGET_PROVINCES  # noqa: E402
_TARGET_REGION_WORDS: list = []
for _city, _prov in _CITY_OF.items():
    if _prov in TARGET_PROVINCES:
        _TARGET_REGION_WORDS.append(_city)
        _TARGET_REGION_WORDS.extend(REGION_COUNTIES.get(_city, []))
_TARGET_REGION_WORDS = list(dict.fromkeys(_TARGET_REGION_WORDS))  # 去重保序


def _region_of(title: str, body: str = "") -> dict:
    """从标题+正文提取地域。标题优先(标题含项目所在地), 正文仅兜底。

    注意: 正文里常含发改委地址「成都市」, 会污染标题里的「眉山」→ 标题优先。
    命中顺序: 先找目标省份(川藏新)县级词 → 市级词 → 县级兜底; 无则正文。
    识别不到返回空 dict(province=""), 由调用方做目标省份过滤(川藏新)。
    """
    def _resolve(words: list, text: str) -> Optional[dict]:
        # 先县级词(更精确), 再市级词
        for ct in words:
            if ct.endswith(("县", "区", "旗", "市")) and ct in text:
                rg = resolve_region("", "", ct)
                if rg.get("matched"):
                    return rg
        for c in words:
            if c in text:
                rg = resolve_region("", c, "")
                if rg.get("matched"):
                    return rg
        return None

    # 标题优先(用目标省份全词表 + 常见词)
    rg = _resolve(_TARGET_REGION_WORDS, title)
    if rg:
        return rg
    rg = _resolve(_REGION_WORDS, title)
    if rg:
        return rg
    # 正文兜底(只在标题无地域时用)
    rg = _resolve(_TARGET_REGION_WORDS, body or "")
    if rg:
        return rg
    rg = _resolve(_REGION_WORDS, body or "")
    if rg:
        return rg
    # 不再默认归四川(避免非目标地域误入库), 返回空
    return {"province": "", "province_label": "", "city": "", "city_label": "",
            "county": "", "county_label": "", "matched": False}


# 公告真实发布日期提取(政务站详情页/URL)
_PUB_DATE_META_RE = re.compile(r'<meta[^>]+name=["\'](?:PubDate|pubdate|ArticlePubDate|createTime)["\'][^>]+content=["\']([\d\- :T]+)["\']', re.IGNORECASE)
_PUB_DATE_TEXT_RE = re.compile(r"(?:发布日期|发布时间|发布时间|发布日期时间|时间)[：:]\s*([\d]{4})[-/.](\d{1,2})[-/.](\d{1,2})")
_PUB_DATE_JSON_RE = re.compile(r'["\'](?:publishTime|pubDate|releaseDate)["\']\s*[:=]\s*["\']?([\d]{4})[-/.](\d{1,2})[-/.](\d{1,2})')


def _parse_publish_date(html: str, text: str, url: str = "") -> Optional[datetime]:
    """从详情页 HTML/正文/URL 提取公告真实发布日期。

    优先级: meta PubDate > 正文「发布日期:」 > JSON 字段 > URL 路径日期(/2026/2/12/xxx.shtml)。
    解析不到返回 None(调用方回退抓取时间)。
    """
    # 1) URL 路径日期: /2026/2/12/xxx.shtml
    m = re.search(r"/(20\d{2})/(\d{1,2})/(\d{1,2})/", url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    # 2) meta / 正文日期标记
    for pat in (_PUB_DATE_META_RE, _PUB_DATE_TEXT_RE, _PUB_DATE_JSON_RE):
        m = pat.search(html)
        if not m:
            continue
        try:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return datetime(y, mo, d)
        except (ValueError, IndexError):
            continue
    # 3) 正文纯文本日期
    m = re.search(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def crawl_intent_source(db: Session, source: WebSource, max_days: int = 365) -> dict:
    """抓取单个政务源: 列表页 → 详情页 → 结构化 → intent_notice。返回统计。

    max_days: 时效窗口(默认近 365 天)。公告真实发布日期超期不入库(意向信息超前性)。
    地域过滤: 仅入库 四川/西藏/新疆 三地, 其他省份公告跳过。
    """
    if not source or not source.url:
        return {"error": "来源无 URL"}
    base = re.match(r"(https?://[^/]+)", source.url)
    base_url = base.group(1) if base else source.url
    html = _fetch(source.url)
    if not html:
        return {"error": "列表页抓取失败", "source": source.name}
    links = _extract_detail_links(html, base_url, limit=20)
    stats = {"source": source.name, "listed": len(links), "stored": 0, "skipped": 0,
             "region_skipped": 0, "stale_skipped": 0, "errors": 0}
    now = datetime.now()
    for url in links:
        try:
            # web_clue 去重: 同 url 已入库则跳过
            existing_clue = db.execute(
                select(WebClue).where(WebClue.url == url, WebClue.is_deleted == False).limit(1)
            ).scalar_one_or_none()
            existing = db.execute(
                select(IntentNotice).where(IntentNotice.url == url, IntentNotice.is_deleted == False).limit(1)
            ).scalar_one_or_none()
            if existing:
                stats["skipped"] += 1
                continue
            detail_html = _fetch(url)
            if not detail_html:
                stats["errors"] += 1
                continue
            title = _extract_title(detail_html)
            body = _extract_body_text(detail_html)
            text = f"{title}\n{body}"

            # 真实发布日期(详情页/正文/URL) + 时效过滤
            published = _parse_publish_date(detail_html, text, url)
            if published and (now - published).days > max_days:
                stats["stale_skipped"] += 1
                continue
            # 地域识别 + 目标省份过滤(川藏新)
            region = _region_of(title, body)
            prov = region.get("province") or ""
            if not prov:
                prov = extract_target_province(text)
            if prov and not is_target_province(prov):
                stats["region_skipped"] += 1
                continue
            if not prov:
                # 无地域信息: 保守跳过(不默认四川)
                stats["region_skipped"] += 1
                continue

            ptype, plabel = _parse_type(title, body)
            amount = _parse_amount(body)
            contact = _parse_contact(body)
            dept = _parse_dept(detail_html, body)
            clue_id = existing_clue.id if existing_clue else None
            intent = IntentNotice(
                clue_id=clue_id, source_id=source.id,
                title=title[:500], url=url, dept=dept[:250] or None,
                project_type=ptype or None, industry=plabel or None,
                amount=amount, contact=contact or None,
                region="".join(filter(None, [region.get("province_label"), region.get("city_label"), region.get("county_label")])) or None,
                province=prov or None,
                city=region.get("city") or None,
                county=region.get("county") or None,
                published_at=published or now, status="new", keywords=source.keywords or None,
                raw_text=body[:3000],
            )
            db.add(intent)
            db.flush()
            stats["stored"] += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("详情处理失败 %s: %s", url, e)
            stats["errors"] += 1
    db.commit()
    return stats


def crawl_all_intent_sources(db: Session) -> dict:
    """抓取所有 scrape_mode='intent' 的启用来源。"""
    sources = db.execute(
        select(WebSource).where(
            WebSource.is_deleted == False,
            WebSource.enabled == True,
            WebSource.scrape_mode == "intent",
        )
    ).scalars().all()
    results = [crawl_intent_source(db, s) for s in sources]
    return {"sources": len(sources), "results": results}
