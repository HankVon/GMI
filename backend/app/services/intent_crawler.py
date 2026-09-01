"""意向性信息爬取服务 — 政务源(发改委/交通厅/自然资源局等)列表+详情 → 结构化 → intent_notice。

流程:
  1. 从 web_source 的 scrape_mode='intent' 来源拉列表页
  2. 提取详情链接(栏目页 common_list.shtml / index 等)
  3. 抓详情页正文, 用 LLM 抽取结构化字段(项目类型/金额/地域/部门/联系人/时间)
  4. 写入 intent_notice(幂等: 同 url 更新)
  5. 与 web_clue 线索库去重(同 url 已有 web_clue 则跳过)

说明: 政务网站多为静态可抓(无验证码), 走 requests/httpx; 若列表页 JS 动态渲染
提取不到链接, 自动降级 crawl4ai 渲染重试(如四川省自然资源厅)。结构化抽取复用
knowledge_extractor 的 LLM 能力。
"""
import json
import logging
import os
import re
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.web_source import WebSource
from app.models.web_clue import WebClue
from app.models.intent_notice import IntentNotice
from app.services.china_regions import resolve_region, is_target_province, extract_target_province
from app.services.intent_quality import apply_quality
from app.services import neo4j_sync

logger = logging.getLogger("intent_crawler")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

# ── 业务地域策略(已确认, 非核心草稿策略) ──
# 仅入库并发布 四川/西藏/新疆 三个目标省份的地质相关业务情报(权威来源见
# china_regions.TARGET_PROVINCES); 其余省份情报在抓取阶段即被过滤, 不入库。
# 川藏新范围内、未达发布质量门槛的意向保留为 draft(草稿), 由审核发布闸门
# intent_quality.can_publish() 控制是否对外发布 —— 非核心业务草稿默认不主动发布,
# 以持续聚焦「川藏新核心地质业务」。本常量仅作策略显式声明, 实际过滤仍以
# TARGET_PROVINCES 为准。
CORE_TARGET_PROVINCES = TARGET_PROVINCES  # ["四川", "西藏", "新疆"]

# 详情链接模式: 兼容常见政务站
# 1) /2026/2/12/xxx.shtml      — 发改委/自然资源厅等
# 2) /202608/t20260820_xxx.htm  — ccgp 中国政府采购网
# 3) /cggg/dfgg/yxgg/xxx.htm    — ccgp 采购意向栏目
_DETAIL_URL_RE = re.compile(
    r'href="([^"]*/(?:20\d{2})/(?:\d{1,2}/\d{1,2})?/[^"]*\.s?html?)"'
    r'|href="([^"]*/cggg/[^"]*\.htm)"'
    r'|href="([^"]*t20\d{6}_[^"]*\.htm)"'
    r'|href="([^"]*/(?:tkq|kyqcr)[^"]*\.htm)"'
    r'|href="([^"]*/20\d{4}/[^"]*\.s?html?)"'
    # 公共资源交易平台矿业权出让详情(无日期路径, .jhtml 后缀, 如 /jyxxkyqtgg/1336239.jhtml)
    r'|href="([^"]*/jyxxky\w*/\d+\.jhtml)"'
    # 西藏公共资源交易: 详情链接写在 onclick="window.open('/xxx.jhtml')" 内
    r'|window\.open\(["\']?([^"\']*/jyxxky\w*/\d+\.jhtml)["\']?\)'
)
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


def _post_list_api(api_url: str, cfg: dict) -> Optional[str]:
    """AJAX 列表接口回退: POST/GET 指定接口拿列表页 HTML(含详情链接)。

    用于静态抓取与 crawl4ai 渲染都提取不到详情链接的 SPA 站点
    (如西藏公共资源交易矿业权出让, 列表经 /search/queryContents.jhtml 异步加载)。
    cfg: {list_method, list_params}
    """
    method = (cfg.get("list_method") or "POST").upper()
    params = cfg.get("list_params") or {}
    try:
        if method == "POST":
            data = urllib.parse.urlencode(params).encode("utf-8")
            r = httpx.post(
                api_url, data=data,
                headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"},
                timeout=20, follow_redirects=True,
            )
        else:
            r = httpx.get(api_url, params=params, headers={"User-Agent": UA},
                          timeout=20, follow_redirects=True)
        if r.status_code == 200:
            return r.text
    except Exception as e:  # noqa: BLE001
        logger.warning("列表 API 请求失败 %s: %s", api_url, e)
    return None


def _extract_detail_links(html: str, base_url: str, limit: int = 20, list_dir: str = "") -> list:
    """从列表页 HTML 提取详情链接(去重, 优先详情页 shtml/htm)。"""
    seen, out = set(), []
    for m in _DETAIL_URL_RE.finditer(html):
        href = next((g for g in m.groups() if g), "").strip()
        if not href:
            continue
        if not href.startswith("http"):
            # ./ 相对路径基于列表页目录; / 绝对路径基于域名根
            if href.startswith("./"):
                href = (list_dir or base_url) + href[1:]  # ./ → /目录
            elif href.startswith("/"):
                href = base_url + href
            else:
                href = (list_dir or base_url) + "/" + href
        # 清理相对路径(../)
        while "/../" in href:
            href = href.replace("/../", "/", 1)
        # 排除列表页自身(常见 /index.htm /list_1.htm 等)
        if re.search(r"/index\.s?html?$|/list(?:_\d+)?\.s?html?$", href):
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append(href)
        if len(out) >= limit:
            break
    return out


def _fetch_rendered_links(url: str, limit: int = 20, page_timeout: int = 60000) -> list:
    """列表页 JS 动态渲染时, 降级 crawl4ai 渲染拿详情链接(带日期标题过滤)。

    适用: 四川省自然资源厅等「标题/日期在静态 HTML, 但 href 由 JS 注入」的站点。
    从渲染后 markdown 提取 `[标题 日期](链接)` 且链接含 /20xx/x/x/ 日期路径的条目。
    返回 [ {url, title, published_at} ], 失败返回 []。
    """
    try:
        from app.services.crawl4ai_client import crawl4ai_client
        data = crawl4ai_client.scrape(url, max_depth=1, page_timeout=page_timeout, extra_delay=2)
    except Exception as e:  # noqa: BLE001
        logger.warning("[intent] crawl4ai 渲染降级失败 %s: %s", url, e)
        return []
    md = data.get("markdown") or ""
    out = []
    seen = set()
    # 匹配 markdown 链接行: [标题 20xx-xx-xx](http...shtml)
    for m in re.finditer(
        r"\[\s*([^\]]+?)\s*(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\s*\]\s*\((https?://[^)]+)\)",
        md,
    ):
        title, url2 = m.group(1).strip(), m.group(5)
        if not re.search(r"/20\d{2}/\d{1,2}/\d{1,2}/", url2):
            continue
        if url2 in seen:
            continue
        seen.add(url2)
        try:
            pub = datetime(int(m.group(2)), int(m.group(3)), int(m.group(4)))
        except ValueError:
            pub = None
        out.append({"url": url2, "title": title, "published_at": pub})
        if len(out) >= limit:
            break
    return out


def _extract_title(html: str) -> str:
    m = re.search(r"<title>([^<]+)</title>", html)
    return m.group(1).strip() if m else ""


def _md_to_text(md: str) -> str:
    """markdown -> 纯文本(去语法符号), 供 SPA 详情页渲染结果做正文提取。"""
    txt = re.sub(r"^#{1,6}\s*", "", md, flags=re.M)
    txt = re.sub(r"\*\*(.+?)\*\*", r"\1", txt)
    txt = re.sub(r"`([^`]+)`", r"\1", txt)
    txt = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", txt)
    txt = re.sub(r"^\s*[-*+]\s+", "", txt, flags=re.M)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


def _md_title(md: str) -> str:
    """从 markdown 提取公告标题: 跳过导航链接行, 匹配含业务关键词的纯文本标题行。"""
    for line in md.splitlines():
        t = line.strip().lstrip("#").strip()
        if not t or "](" in t or "http" in t:
            continue
        if any(k in t for k in ("出让公告", "探矿权", "采矿权", "矿业权",
                                "挂牌出让", "出让结果", "成交公示", "招标公告", "中标公告")):
            return t
    m = re.search(r"^#\s+(.+)$", md, re.M)
    return m.group(1).strip() if m else ""


def _fetch_rendered_detail(url: str, page_timeout: int = 120000) -> Optional[tuple]:
    """SPA 详情页(如西藏公共资源交易)静态抓取正文为空时, crawl4ai 渲染拿正文。
    返回 (markdown, title, body) 或 None。
    """
    try:
        from app.services.crawl4ai_client import crawl4ai_client
        data = crawl4ai_client.scrape(url, max_depth=1, page_timeout=page_timeout, extra_delay=2)
        md = data.get("markdown") or ""
        if len(md) < 100:
            return None
        title = _md_title(md) or data.get("title") or ""
        body = _md_to_text(md)
        if len(body) < 100:
            return None
        return (md, title, body)
    except Exception as e:  # noqa: BLE001
        logger.warning("[intent] 详情页渲染降级失败 %s: %s", url, e)
        return None


# 正文噪音行(导航/面包屑/操作按钮/版权等), 命中即删除
_NOISE_LINE_RE = re.compile(
    r"^(注册|登录|中国政府网|矿业权市场|首页|机构|动态|公开|服务|互动|数据|专题|搜索|"
    r"网站首页|无障碍|繁体|简体版|English|政务邮箱|使用帮助|收藏本站|设为首页|"
    r"大|中|小|打印|关闭|分享|收藏|字体|返回顶部|"
    r"您现在的位置|当前位置|网站位置|信息位置|"
    r"版权所有|主办单位|承办单位|ICP备|网站标识码|建议使用|技术支持|"
    r"-->\s*$|^&nbsp;|^\s*>\s*$)"
)
# Vue 模板残留 / 属性残留 / JS 插值(如 '+$parent.NA_NOTICE_NO+')
_VUE_RESIDUE_RE = re.compile(
    r"-1\?'[^']*':'[^']*'|__ko__\w*=|\{\{[^}]*\}\}|\bko\d+\b|"
    r"'\+[^']*\+'|\"\+\$[A-Za-z_\.]+\+\"|\$\w+\.\w+|'\+[^']*\+'\"?\s*>?"
)
# 正文起点(之前的内容视为页面头/面包屑, 丢弃)
_BODY_START_RE = re.compile(
    r"^[（(]公告文号|^根据《|^[一二三四五六七八九十]+、|^出让公告|^挂牌出让|^探矿权挂牌|^采矿权挂牌|"
    r"矿业权挂牌出让公告|关于.*出让公告|^受.*委托|^按照《"
)


def _extract_body_text(html: str) -> str:
    """正文提取: 优先正文起点定位; 表格保序; 解码实体; 清洗导航/面包屑/Vue残留/操作噪音。"""
    # 去掉 script/style
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # 1) 正文起点 marker 定位(公告类站点最可靠: 从公告文号/法律依据/第一节开始)
    block = None
    for mk in ("（公告文号", "(公告文号", "根据《", "一、出让人", "出让人", "一、项目概况", "受委托", "按照《"):
        i = html.find(mk)
        # 跳过 JS 模板伪文号(如（公告文号：'+$parent.NA_NOTICE_NO+'）)
        while i > 0 and re.search(r"\$\w+\.\w+|\+[\"']", html[max(0, i - 10): i + 60]):
            i = html.find(mk, i + 1)
        if i > 80:
            block = html[i:]
            break
    # 2) 标准正文容器兜底
    if block is None:
        for pat in (
            r'id="cmsArticleContent"',
            r'id="articleContent"',
            r'class="view[^"]*TRS_UEDITOR[^"]*"',
            r'class="[^"]*(?:content|article|TRS_Editor|view|xxgk-content|newsContent)[^"]*"',
            r'id="[^"]*(?:content|article)[^"]*"',
        ):
            m = re.search(r"<div[^>]*" + pat + r"[^>]*>(.*?)</div>", html, re.DOTALL | re.IGNORECASE)
            if m and len(re.sub(r"<[^>]+>", "", m.group(1)).strip()) > 20:
                block = m.group(1)
                break
    if block is None:
        block = html
    # 表格 → 行列文本(保留结构)
    def _table_repl(m: re.Match) -> str:
        tbl = m.group(0)
        rows = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbl, re.DOTALL):
            cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.DOTALL)
            row = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
            row = [c for c in row if c]
            if row:
                rows.append(" | ".join(row))
        return "\n[表格]\n" + "\n".join(rows) + "\n[/表格]\n" if rows else ""
    block = re.sub(r"<table.*?</table>", _table_repl, block, flags=re.DOTALL | re.IGNORECASE)
    # 解码 HTML 实体
    import html as _html_mod
    block = _html_mod.unescape(block)
    # 标签 → 换行
    text = re.sub(r"<[^>]+>", "\n", block)
    text = re.sub(r"\s*\n\s*", "\n", text)
    lines = [re.sub(_VUE_RESIDUE_RE, "", l).strip() for l in text.splitlines() if l.strip()]
    # 正文起点截断
    start = None
    for i, l in enumerate(lines):
        if _BODY_START_RE.search(l):
            start = i
            break
    if start is not None:
        lines = lines[start:]
    # 页脚/站内导航截断: 遇到即丢弃其后所有内容(避免混入底部导航/版权/链接列表)
    _FOOTER_RE = re.compile(
        r"网站地图|关于本站|联系我们|网站调查|网站声明|政府网站标识码|"
        r"版权所有|主办单位|承办单位|技术支持|ICP备|京公网安备|建议使用|"
        r"页面纠错|网站纠错|智能问答|无障碍浏览|返回首页|长者专区|"
        r"相关链接|市州自然资源|州自然资源门户|各省自然资源厅|"
        r"---?[\s\-]*市州|—\s*市州|市级自然资源|县级自然资源"
    )
    for i, l in enumerate(lines):
        if _FOOTER_RE.search(l):
            lines = lines[:i]
            break
    # 噪音行过滤(整行) + 相邻去重
    out, prev = [], ""
    for l in lines:
        if _NOISE_LINE_RE.match(l):
            continue
        if l == prev:
            continue
        prev = l
        out.append(l)
    lines = out

    # 字段断裂合并: "标签：\n值\n单位" → "标签：值单位"; 每个标签独立成行
    merged = []
    i = 0
    while i < len(lines):
        l = lines[i]
        m = re.match(r"^(.{1,20}[：:])$", l)
        if m and i + 1 < len(lines):
            label = m.group(1)
            j = i + 1
            parts = []
            # 值区: 收集直到下一个 "标签："(以冒号结尾) / 行内含"标签：值" / 小节标题
            while j < len(lines):
                nxt = lines[j]
                if (re.match(r"^.{1,20}[：:]$", nxt)
                        or re.match(r"^[一二三四五六七八九十]+、", nxt)
                        or re.match(r"^.{1,16}[：:].+$", nxt)):  # 行内含"标签：值"
                    break
                parts.append(nxt)
                j += 1
            if parts:
                merged.append(label + "".join(parts))
                i = j
                continue
        merged.append(l)
        i += 1
    lines = merged
    # 行内多字段拆分: 一行含多个"标签：值"时拆成多行(如"名称：A勘查矿种：B" → 两行)
    split_lines = []
    for l in lines:
        hits = list(re.finditer(r"[\u4e00-\u9fa5A-Za-z（）()]{1,16}[：:]", l))
        if len(hits) > 1:
            segs = []
            for k, hm in enumerate(hits):
                end = hits[k + 1].start() if k + 1 < len(hits) else len(l)
                segs.append(l[hm.start():end].strip())
            split_lines.extend(segs)
        else:
            split_lines.append(l)
    lines = split_lines
    # 清理残留引号/尖括号碎片(如 " ""> / >项目 / ""> )
    lines = [re.sub(r'\s*["""]+\s*>?[\s>]*["""]?\s*', "", l).strip() for l in lines]
    lines = [re.sub(r'^>+|>+$', "", l).strip() for l in lines]
    lines = [l for l in lines if l and l not in ('"', '"', ">", '""')]
    return "\n".join(lines).strip()[:8000]


_ATTACHMENT_RE = re.compile(
    r'<a[^>]*href="([^"]*\.(?:pdf|doc|docx|xls|xlsx|rar|zip|7z)(?:\?[^"]*)?)"[^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)


def _extract_attachments(html: str, page_url: str) -> list:
    """从详情页 HTML 提取附件链接(pdf/doc/xls 等), 返回 [{url,name}]。"""
    if not html:
        return []
    host = (re.match(r"(https?://[^/]+)", page_url) or [None, ""])[1] if re.match(r"(https?://[^/]+)", page_url) else ""
    base = page_url.rpartition("/")[0]
    out, seen = [], set()
    for m in _ATTACHMENT_RE.finditer(html):
        href = m.group(1).strip()
        name = re.sub(r"<[^>]+>", "", m.group(2)).strip() or href.split("/")[-1]
        if href.startswith("//"):
            href = "https:" + href
        elif not href.startswith("http"):
            if href.startswith("./"):
                href = base + href[1:]
            elif href.startswith("/"):
                href = host + href
            else:
                href = base + "/" + href
        if href in seen:
            continue
        seen.add(href)
        out.append({"url": href, "name": name[:200]})
        if len(out) >= 10:
            break
    return out


def _download_attachments(intent_id: int, attachments: list, base_dir: str) -> list:
    """下载附件到 uploads/intent_attachments/{intent_id}/, 返回落库记录 [{file_name,local_path,remote_url,file_size}]。"""
    import os
    saved = []
    if not attachments:
        return saved
    target = os.path.join(base_dir, "intent_attachments", str(intent_id))
    os.makedirs(target, exist_ok=True)
    from urllib.parse import quote
    for att in attachments:
        try:
            req_url = quote(att["url"], safe=":/?=&%+")
            r = httpx.get(req_url, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
            if r.status_code != 200 or len(r.content) < 100:
                continue
            fname = att["url"].split("/")[-1].split("?")[0]
            if not fname or "." not in fname:
                fname = f"attachment_{len(saved)+1}.pdf"
            fname = re.sub(r"[^\w.\-\u4e00-\u9fa5]", "_", fname)
            path = os.path.join(target, fname)
            with open(path, "wb") as f:
                f.write(r.content)
            saved.append({
                "file_name": fname,
                "local_path": os.path.relpath(path, base_dir),  # uploads/...
                "remote_url": att["url"],
                "file_size": len(r.content),
            })
        except Exception as e:  # noqa: BLE001
            logger.warning("附件下载失败 %s: %s", att["url"], e)
    return saved


def _save_attachments(db, intent_id: int, attachments: list):
    """下载附件到 uploads/ 并落库 intent_attachment(幂等: 同 remote_url 跳过)。"""
    from app.models.intent_attachment import IntentAttachment
    from app.utils.upload_paths import upload_root
    if not attachments:
        return
    base_dir = str(upload_root())
    saved = _download_attachments(intent_id, attachments, base_dir)
    if not saved:
        return
    for att in saved:
        exists = db.execute(
            select(IntentAttachment).where(
                IntentAttachment.intent_id == intent_id,
                IntentAttachment.remote_url == att["remote_url"],
                IntentAttachment.is_deleted == False,
            )
        ).scalar_one_or_none()
        if exists:
            continue
        db.add(IntentAttachment(
            intent_id=intent_id,
            file_name=att["file_name"],
            local_path=att["local_path"],
            remote_url=att["remote_url"],
            file_size=att["file_size"],
        ))
    db.flush()


# 非目标省份(除川藏新外的省级行政区), 用于矿业权放宽时的反向排除, 保持商机池聚焦川藏新
_NON_TARGET_PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
    "湖北", "湖南", "广东", "广西", "海南", "重庆", "贵州", "云南",
    "陕西", "甘肃", "青海", "宁夏",
]

# 公司业务白名单关键词(标题/正文命中即视为相关意向, 未识别类型的兜底判断)
# 业务: 地质灾害治理 / 生态修复 / 矿山修复 / 水土保持 / 地质勘察与监测
_BUSINESS_KEYWORDS = [
    # 地质灾害
    "地质灾害", "地灾", "滑坡", "泥石流", "崩塌", "地面塌陷", "隐患治理", "排危", "避险搬迁", "边坡治理",
    # 生态修复
    "生态修复", "生态治理", "环境治理", "生态保护", "矿山修复", "矿山地质", "恢复治理", "山水林田湖草",
    "废弃矿山", "综合治理", "土地整治", "复垦", "绿化工程", "林草植被", "荒漠化治理",
    # 水土保持
    "水土保持", "水土流失", "坡耕地", "小流域治理", "水土保持方案",
    # 地质勘察/监测
    "地质勘察", "地质勘查", "工程勘察", "岩土", "勘察", "钻探", "监测预警", "地质环境监测", "测绘",
    "地灾评估", "危险性评估", "勘查设计", "勘察设计",
    # 矿业/矿产/勘查(评审公示、采矿权、探矿权等核心意向)
    "矿业权", "采矿权", "探矿权", "采矿", "探矿", "矿产", "矿权", "勘查方案", "勘查区块",
    "地质找矿", "有色金属", "铅锌矿", "铜矿", "金矿", "磷矿", "煤", "页岩气", "矿山",
    "出让公告", "挂牌出让", "储量核实", "资源储量", "矿业", "选矿", "冶炼",
]
# 明确无关类型: 命中即跳过(即使正文含「治理」等宽泛词)
_NON_BUSINESS_TYPES = {"transport", "energy", "municipal", "education", "healthcare"}
# 标题硬排除词: 命中即跳过(防正文宽泛词误放行, 如 220千伏供电工程正文含「勘察/生态」)
_TITLE_EXCLUDE_KW = (
    "千伏", "供电工程", "输变电", "输电线路", "变电站", "储能", "电站", "电网",
    "光伏", "风电", "发电", "天然气", "输气", "管道", "数据中心", "5G", "基站",
    "铁路", "公路", "高速公路", "桥梁", "码头", "机场", "隧道",
    "污水", "供水", "排水", "管网", "市政道路", "学校", "医院",
    # 新闻/政策/活动(非商机意向): 标题命中即跳过
    "主场活动", "启动仪式", "工作座谈", "调研", "督导", "培训会", "现场会", "交流会",
    "情况报告", "下达情况", "名单公示", "拟资助", "资助课题", "评选结果",
)


def _is_business_relevant(title: str, body: str, ptype: str) -> bool:
    """判断是否与公司业务相关。

    策略(业务关键词优先于排除词, 避免「XX滑坡治理(涉G318国道)」等地灾/生态项目
    因标题含「公路/隧道」被误杀):
    1. 标题命中业务关键词 → 保留(标题最可靠, 优先)
    2. 标题命中硬排除词(供电/输变电/储能/公路等) → 跳过
    3. 正文命中业务关键词 → 保留(兜底)
    4. 类型命中明确无关(公路/能源/市政/教育/医疗) → 跳过
    5. 其余 → 跳过(宁缺毋滥)
    """
    if any(k in title for k in _BUSINESS_KEYWORDS):
        return True
    if any(k in title for k in _TITLE_EXCLUDE_KW):
        return False
    if any(k in body for k in _BUSINESS_KEYWORDS):
        return True
    if ptype in _NON_BUSINESS_TYPES:
        return False
    return False


# 项目类型关键词(从标题/正文识别, 与 business_network 专长映射对齐)
# 注意: 数组顺序即优先级, transport(公路/铁路)这类应排最前, 避免被正文「地质灾害防治」误抢
_TYPE_KEYWORDS = [
    # ── 核心业务优先匹配 ──
    # 原因: _parse_type 按本表顺序取第一个命中词。若把 transport/energy 放前面,
    # 「XX矿勘查探矿权出让」等矿业公告会因正文提到「公路/隧道」而被误判为交通工程。
    ("地质灾害", "geo_hazard"), ("地灾", "geo_hazard"), ("滑坡", "geo_hazard"), ("泥石流", "geo_hazard"),
    ("监测预警", "geo_hazard"), ("预警指挥", "geo_hazard"), ("应急能力提升", "geo_hazard"), ("可研", "geo_hazard"),
    ("地质勘察", "geo_survey"), ("地质勘查", "geo_survey"), ("工程勘察", "geo_survey"), ("岩土", "geo_survey"),
    ("勘查区块", "geo_survey"), ("勘查方案", "geo_survey"),
    ("生态修复", "eco_restoration"), ("环境治理", "eco_restoration"),
    ("节能审查", "eco_restoration"), ("固废", "eco_restoration"), ("资源综合利用", "eco_restoration"),
    ("矿业权", "mining_rights"), ("采矿权", "mining_rights"), ("探矿权", "mining_rights"),
    ("采矿", "mining_rights"), ("矿产资源", "mining_rights"), ("矿山", "mining_rights"),
    ("矿权", "mining_rights"), ("页岩气", "mining_rights"),
    # 单独的「勘查」(置于地质勘查/勘查方案之后, 避免抢走勘察类): 覆盖「XX矿勘查探矿权出让」
    ("勘查", "mining_rights"),
    # ── 非核心业务(靠后匹配) ──
    ("公路", "transport"), ("铁路", "transport"), ("高速", "transport"),
    ("桥梁", "transport"), ("隧道", "transport"), ("机场", "transport"), ("码头", "transport"),
    ("水电", "energy"), ("光伏", "energy"), ("风电", "energy"), ("天然气", "energy"),
    ("千伏", "energy"), ("供电工程", "energy"), ("输变电", "energy"), ("储能", "energy"),
    ("电站", "energy"), ("电网", "energy"), ("发电", "energy"), ("输电", "energy"),
    ("行动方案", "policy"), ("三年行动方案", "policy"), ("指导意见", "policy"), ("科技创新", "policy"),
    ("市政", "municipal"), ("管网", "municipal"), ("供水", "municipal"), ("污水", "municipal"),
    ("水利", "water"), ("水库", "water"), ("堤防", "water"),
    ("学校", "education"), ("医院", "healthcare"),
]

_TYPE_LABELS = {
    "geo_hazard": "地质灾害治理", "geo_survey": "地质勘察", "eco_restoration": "生态修复",
    "mining_rights": "矿业权", "transport": "交通工程", "energy": "能源工程",
    "municipal": "市政工程", "water": "水利工程", "education": "教育设施", "healthcare": "医疗设施",
}

# 金额关键词: 覆盖常规批复(总投资/投资/估算/预算)与矿业权出让(起始价/出让收益)、
# 采购(采购预算)及合同/中标类。
_AMOUNT_RE = re.compile(
    r"(?:总投资|投资[总估]?额?|估算[总]?投资|项目总投资|预算[金额]*|概算[投资]*|采购预算|"
    r"起始价|挂牌起始价|出让起始价|出让收益|中标价|中标金额|合同[总]?价|合同金额)"
    r"[约\s]*[:：]?\s*(?:人民币)?\s*(?:¥|￥)?\s*([\d,，.]+)\s*(?:亿|万元?|万)"
)
_AMOUNT_UNIT = {"亿": 10000, "万": 1, "万元": 1}


def _parse_amount(text: str) -> Optional[float]:
    """从正文提取金额(万元)。支持 亿/万; 兼容 起始价/保证金/采购预算/合同价 等写法。

    会议/调度/座谈等非批复类新闻的「2026年度」「3400人次」等数字不算金额,
    需金额关键词(总投资/起始价/采购预算 等)紧邻数字。
    """
    if any(k in text for k in ("会议", "调度", "座谈", "专题会", "调研", "培训", "讲话", "致辞")):
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
    """提取联系人/电话(跨行覆盖多个电话, 但限制长度, 避免吞入正文)。"""
    m = re.search(
        r"(?:联系人|联系电话|联系单位|联系部门|代理机构|招标代理|出让人|受让人|咨询电话|业务咨询)[：:]\s*"
        r"((?:[^\n]|[\n\r]){2,200}?)(?=\n[一二三四五六七八九十]+、|\n\s*[A-Z]|\n\s*$|\Z)",
        text,
    )
    if not m:
        m = re.search(r"(?:联系人|联系电话|联系单位)[：:]\s*([^\n]{2,120})", text)
    if m:
        out = re.sub(r"\s+", " ", m.group(1)).strip()
        # 仅保留含电话/联系人特征的内容, 防止吞入大段正文
        phone = re.search(r"(?:[0-9]{3,4}-?[0-9]{7,8}|[0-9]{8,12}|1[3-9]\d{9})", out)
        if phone:
            seg = out[: phone.start() + 40]
            return seg[:160]
        return out[:60]
    return ""


def _parse_dept(html: str, text: str) -> str:
    m = re.search(r"<meta name=\"ContentSource\" content=\"([^\"]+)\"", html)
    if m:
        return m.group(1).strip()
    m = re.search(r"发文机关[：:]\s*([^\n<]{2,40})", text)
    if m:
        return m.group(1).strip()
    # 矿业权出让公告: "一、出让人\n名称：\n四川省自然资源厅\n场所：..." / "发布单位"
    m = re.search(r"名称[：:]\s*([\u4e00-\u9fa5A-Za-z0-9（）()]{2,40}?)(?=\s*\n?\s*(?:场所[：:]|\d{4}年|\s*$))", text)
    if m and any(k in m.group(1) for k in ("自然资源厅", "自然资源和规划局", "交易服务中心", "发改委", "林草局", "生态环境", "自然资源局", "公共资源")):
        return m.group(1).strip()
    m = re.search(r"发布单位[：:]\s*([^\n<]{2,40})", text)
    if m:
        return m.group(1).strip()
    # 正文末尾署名(常见于公告落款: 四川省自然资源厅\n2026年)
    m = re.search(r"([\u4e00-\u9fa5]{4,30}?(?:自然资源厅|自然资源和规划局|发展和改革委员会|发展改革委|生态环境厅|公共资源交易服务中心|林草局|自然资源局))\s*\n?\s*\d{4}年", text)
    if m:
        return m.group(1).strip()
    return ""


# 批复/公示文号: 川发改基础〔2026〕227号 / 川自然资函〔2026〕88号 / (川发改基础〔2026〕227号)
_DOC_NO_RE = re.compile(r"([\u4e00-\u9fa5A-Za-z]{2,12}?)\s*〔\s*(\d{4})\s*〕\s*(\d+)\s*号?")
# 项目业主/建设单位 常见句式
_UNIT_PATTERNS = [
    (re.compile(r"项目业主单位为\s*([^\n，。；;]{4,60})"), 1),
    (re.compile(r"项目建设单位为\s*([^\n，。；;]{4,60})"), 1),
    (re.compile(r"项目单位为\s*([^\n，。；;]{4,60})"), 1),
    (re.compile(r"由\s*([\u4e00-\u9fa5A-Za-z0-9（）()]{6,50}?)\s*作为项目业主"), 1),
]


def _parse_project_unit(body: str) -> Optional[str]:
    """从发改委批复正文提取项目业主/建设单位。

    批复正文常见句式:
      - 「项目业主单位为XX集团有限公司。」
      - 「同意建设XX。项目业主单位为XX。」
    返回单位名(去「有限公司」等尾缀前的核心名), 无则 None。
    """
    for pat, _ in _UNIT_PATTERNS:
        m = pat.search(body)
        if m:
            return m.group(1).strip()
    return None


def _parse_doc_no(text: str) -> Optional[str]:
    """提取批复文号(如 川发改基础〔2026〕227号)。"""
    m = _DOC_NO_RE.search(text)
    if m:
        return f"{m.group(1)}〔{m.group(2)}〕{m.group(3)}号"
    return None


def _normalize_unit(name: str) -> str:
    """单位名规范化: 去空白/「有限(责任)公司」等尾缀/括号内容, 便于模糊匹配。"""
    n = re.sub(r"\s+", "", name or "")
    n = re.sub(r"[（(].*?[)）]", "", n)
    n = re.sub(r"(有限[责任]*公司|有限责任公司|股份有限公司|集团有限公司?|公司)$", "", n)
    return n


def _match_unit_to_company(db: Session, unit_name: str) -> Optional[dict]:
    """把解析出的项目业主单位与 company 库做模糊匹配。

    匹配策略: 规范化后
      1) 精确名/简称 equal
      2) company.name 包含业主核心名(如「四川省XX地质灾害防治工程有限公司」含「XX」)
      3) 业主名含 company 核心名
    返回 {"company_id", "name", "match_type"} 或 None。只读查询, 不做写。
    """
    if not unit_name:
        return None
    core = _normalize_unit(unit_name)
    if len(core) < 4:
        return None
    from app.models.company import Company
    rows = db.execute(
        select(Company).where(
            Company.is_deleted == False,
            Company.name.like(f"%{core[:8]}%"),
        ).limit(20)
    ).scalars().all()
    for c in rows:
        cname = _normalize_unit(c.name)
        if not cname:
            continue
        # 精确匹配
        if cname == core or c.short_name == unit_name:
            return {"company_id": c.id, "name": c.name, "match_type": "exact"}
    for c in rows:
        cname = _normalize_unit(c.name)
        # 业主名含公司核心名(去掉尾缀后 4+ 字连续子串命中)
        if core in cname or (len(core) >= 6 and core[:-2] in cname):
            return {"company_id": c.id, "name": c.name, "match_type": "contains"}
    return None


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
    # 1) URL 路径日期: /2026/2/12/xxx.shtml 或 /cggg/dfgg/yxgg/202608/t20260820_xxx.htm
    m = re.search(r"/(20\d{2})/(\d{1,2})/(\d{1,2})/", url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = re.search(r"t(20\d{2})(\d{2})(\d{2})_", url)
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


def _sync_intent_to_neo4j(db: Session, intent: IntentNotice, matched_entity: Optional[dict]) -> None:
    """把意向节点 + 与已匹配单位的 RELATES_TO 边同步到 Neo4j。

    意向作为独立节点入图谱, 使情报动态详情可展示「意向专属子图」;
    仅当 matched_entity 匹配到 company 库时建立 (Intent)-[:RELATES_TO]->(Company) 边。
    Neo4j 不可用时静默降级, 不阻断 MySQL 主流程。
    """
    try:
        amount_wan = float(intent.amount) if intent.amount is not None else None
        neo4j_sync.sync_intent(
            intent_id=intent.id, title=intent.title,
            region=intent.region or "", amount_wan=amount_wan,
            dept=intent.dept or "", status=intent.status or "new",
        )
        if matched_entity and matched_entity.get("company_id"):
            neo4j_sync.register_open_relation("RELATES_TO", "相关于")
            neo4j_sync.sync_open_relation(
                source_type="intent", source_id=intent.id, source_name=intent.title,
                target_type="company", target_id=int(matched_entity["company_id"]),
                target_name=matched_entity.get("company") or "",
                relation_key="RELATES_TO", relation_zh="相关于",
                confidence=0.9, evidence=f"业主单位匹配:{matched_entity.get('unit', '')}",
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("意向同步 Neo4j 失败(已降级): %s", e)


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
    rendered_items: list = []
    if not html:
        # 静态抓取失败(403 反爬等) → 降级 crawl4ai 真实浏览器渲染
        rendered_items = _fetch_rendered_links(source.url, limit=20)
        if not rendered_items:
            return {"error": "列表页抓取失败", "source": source.name}
    # 相对链接(./xxx)基于列表页目录解析; 绝对路径基于域名根
    list_dir = source.url.rpartition("/")[0]
    links = _extract_detail_links(html or "", base_url, list_dir=list_dir, limit=20) \
        if html else [it["url"] for it in rendered_items]
    # AJAX 接口分页站点: 静态/渲染都拿不到链接时, 回退到 query_config 定义的列表 API
    if not links and source.query_config:
        try:
            _cfg = json.loads(source.query_config or "{}")
            _api = _cfg.get("list_api")
            if _api:
                if not _api.startswith("http"):
                    _api = base_url + _api
                _list_html = _post_list_api(_api, _cfg)
                if _list_html:
                    links = _extract_detail_links(_list_html, base_url, list_dir=list_dir, limit=20)
        except Exception as e:  # noqa: BLE001
            logger.warning("列表 API 抓取失败 %s: %s", source.name, e)
    rendered = bool(rendered_items)
    # 静态列表提取不到链接(JS 动态渲染/反爬 403 页面无详情链接) → 降级 crawl4ai 渲染
    if not links:
        rendered_items = _fetch_rendered_links(source.url, limit=20)
        if rendered_items:
            links = [it["url"] for it in rendered_items]
            rendered = True
    stats = {"source": source.name, "listed": len(links), "stored": 0, "skipped": 0,
             "region_skipped": 0, "stale_skipped": 0, "errors": 0, "rendered": rendered}
    now = datetime.now()
    rendered_by_url = {it["url"]: it for it in (rendered_items if rendered else [])}
    for url in links:
        try:
            # web_clue 去重: 同 url 已入库则跳过
            existing_clue = db.execute(
                select(WebClue).where(WebClue.url == url, WebClue.is_deleted == False).limit(1)
            ).scalar_one_or_none()
            existing = db.execute(
                select(IntentNotice).where(IntentNotice.url == url, IntentNotice.is_deleted == False).limit(1)
            ).scalar_one_or_none()
            # 已存在且正文完整(≥60字) → 跳过; 正文缺失/过短(旧抓取只抓到标题) → 仍抓详情以补全正文
            need_refresh = bool(existing) and len((existing.raw_text or "").strip()) < 60
            if existing and not need_refresh:
                stats["skipped"] += 1
                continue
            detail_html = _fetch(url)
            if not detail_html:
                stats["errors"] += 1
                continue
            title = _extract_title(detail_html)
            body = _extract_body_text(detail_html)
            # SPA 详情页(如西藏公共资源交易)静态正文多为导航框架(<400字) → crawl4ai 渲染回退
            if len(body or "") < 400:
                rdata = _fetch_rendered_detail(url)
                if rdata:
                    detail_html, title, body = rdata
            text = f"{title}\n{body}"
            attachments = _extract_attachments(detail_html, url)
            # 渲染来源的列表标题优先(静态标题常为栏目名), 日期复用渲染结果
            ritem = rendered_by_url.get(url)
            if ritem and ritem.get("title") and len(ritem["title"]) > len(title):
                title = ritem["title"]

            # 真实发布日期(详情页/正文/URL) + 渲染日期兜底 + 时效过滤
            published = _parse_publish_date(detail_html, text, url)
            if not published and ritem and ritem.get("published_at"):
                published = ritem["published_at"]
            if published and (now - published).days > max_days:
                stats["stale_skipped"] += 1
                continue
            # 地域识别 + 目标省份过滤(川藏新)
            region = _region_of(title, body)
            prov = region.get("province") or ""
            if not prov:
                prov = extract_target_province(text)
            # 矿业权类: 全国性强商机, 放宽地域, 但排除明确非川藏新的省份(保持业务聚焦)
            is_mining = any(k in title for k in ("矿业权", "采矿权", "探矿权", "采矿", "探矿", "矿权", "矿产"))
            if is_mining:
                _non_target = [p for p in _NON_TARGET_PROVINCES if p in (title + body)]
                _target = [p for p in ("四川", "西藏", "新疆") if p in (title + body)]
                if _non_target and not _target:
                    stats["region_skipped"] += 1
                    continue
                # 川藏新 或 无法判定省份(全国性公告) → 放行(进后台待审, 人工可控)
            else:
                if prov and not is_target_province(prov):
                    stats["region_skipped"] += 1
                    continue
                if not prov:
                    # 非矿业权且无地域信息: 保守跳过(不默认四川)
                    stats["region_skipped"] += 1
                    continue

            # region 字符串: 市县缺省时用省份兜底(如仅识别到「四川」→「四川省」)
            _prov_label = (region.get("province_label") or "")
            if not _prov_label and prov:
                _prov_label = prov + ("省" if not prov.endswith(("省", "市", "自治区", "区")) else "")
            region_str = "".join(filter(None, [_prov_label,
                                               region.get("city_label"),
                                               region.get("county_label")])) or None

            ptype, plabel = _parse_type(title, body)
            # 业务相关性过滤: 命中无关类型(公路/能源/市政等)或未命中业务关键词 → 跳过
            if not _is_business_relevant(title, body, ptype):
                stats["biz_skipped"] = stats.get("biz_skipped", 0) + 1
                continue
            amount = _parse_amount(body)
            contact = _parse_contact(body)
            dept = _parse_dept(detail_html, body)
            # 发改委批复: 提取项目业主单位 → 关联 company 库(写入 matched_entity)
            project_unit = _parse_project_unit(body)
            matched_entity = None
            if project_unit:
                m = _match_unit_to_company(db, project_unit)
                matched_entity = {
                    "unit": project_unit,
                    "doc_no": _parse_doc_no(text) or None,
                    "matched": bool(m),
                    **({"company_id": m["company_id"], "company": m["name"], "match_type": m["match_type"]} if m else {}),
                }
            clue_id = existing_clue.id if existing_clue else None
            if need_refresh and existing:
                # 旧抓取正文缺失: 更新正文及结构化字段(不新建)
                existing.raw_text = body[:8000]
                existing.title = title[:500]
                existing.dept = dept[:250] or None
                existing.project_type = ptype or None
                existing.industry = plabel or None
                existing.amount = amount
                existing.contact = contact or None
                existing.region = region_str or None
                existing.province = prov or None
                existing.city = region.get("city") or None
                existing.county = region.get("county") or None
                existing.published_at = published or existing.published_at or now
                existing.status = "new"
                existing.keywords = source.keywords or existing.keywords or None
                existing.matched_entity = json.dumps(matched_entity, ensure_ascii=False) if matched_entity else None
                db.flush()
                apply_quality(existing)  # 入库即体检: 结果写 ext_attrs.quality
                _save_attachments(db, existing.id, attachments)
                _sync_intent_to_neo4j(db, existing, matched_entity)
                stats["stored"] += 1
                continue
            intent = IntentNotice(
                clue_id=clue_id, source_id=source.id,
                title=title[:500], url=url, dept=dept[:250] or None,
                project_type=ptype or None, industry=plabel or None,
                amount=amount, contact=contact or None,
                region=region_str,
                province=prov or None,
                city=region.get("city") or None,
                county=region.get("county") or None,
                published_at=published or now, status="new", keywords=source.keywords or None,
                matched_entity=json.dumps(matched_entity, ensure_ascii=False) if matched_entity else None,
                raw_text=body[:8000],
            )
            db.add(intent)
            db.flush()
            apply_quality(intent)  # 入库即体检: 结果写 ext_attrs.quality
            _save_attachments(db, intent.id, attachments)
            _sync_intent_to_neo4j(db, intent, matched_entity)
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
