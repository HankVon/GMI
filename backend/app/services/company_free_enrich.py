"""单位信息免费补全服务 — 不依赖付费 API。

补全渠道(按优先级):
  1. web_clue 公告库匹配: 从已抓取的四川政府采购网公告 meta 中按采购人名称匹配,
     提取 purchaserLinkPhone(电话)/purchaserAddr(地址)。零网络、即时。
  2. 主动检索四川政府采购网: 用 crawl4ai query_crawl 按单位名检索公告,
     从公告 meta 提取采购人电话/地址。免费、权威(政府采购公告公开数据)。
  3. 企查查: 保留为兜底(有 API 配额时), 见 company_enrich.enrich_company_sync。

原则: 只填空字段、不覆盖已有信息; 查不到的如实返回 message, 绝不编造。
"""
import json
import logging
import re
from typing import Optional
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.web_clue import WebClue
from app.services.crawl4ai_client import crawl4ai_client

logger = logging.getLogger("company_enrich")

# 占位符: 单位表历史数据用 "/" "-" "无" 等表示「无信息」, 需视为空白
_PLACEHOLDERS = {"", "/", "-", "—", "无", "暂无", "null", "none", "nan"}


def _is_blank(v) -> bool:
    """字段是否有真实值: 空字符串 / None / 占位符(/, -, 无等) 都视为空白。"""
    if v is None:
        return True
    s = str(v).strip()
    return s.lower() in _PLACEHOLDERS


# 四川政府采购网查询式抓取配置(与 web_source id=2 保持一致)
# purchaser_placeholder: 按「采购人」框检索单位名(公告标题常不含采购人全名,
# 按标题搜不到; 采购人框才能精准命中该单位的全部公告)
_CCGP_URL = "https://www.ccgp-sichuan.gov.cn/maincms-web/noticeInformation?typeId=ggxx"
_CCGP_QUERY_CONFIG = {
    "captcha_placeholder": "验证码",
    "query_button_text": "查询",
    "captcha_img_keyword": "getVerify",
    "api_url_keyword": "selectInfoForIndex",
    "result_rows_jsonpath": "data.rows",
    "captcha_refresh_keyword": "换一张",
    "purchaser_placeholder": "采购人",
}

_PHONE_RE = re.compile(r"[\d\-\s]{7,20}")
# 法定代表人 提取: 支持「法定代表人:郑勇」「法定代表人为郑勇」「法人代表：郑勇」等
_LEGAL_RE = re.compile(r"(?:法定代表人|法人代表)[为是]?[:：]?\s*([\u4e00-\u9fa5·]{2,4})")

# ---- 百度搜索补全 ----
# 座机: 0xx-xxxxxxx / 0xxx-xxxxxxxx / 带空格; 手机: 1[3-9]xxxxxxxxx
_PHONE_PATTERN = re.compile(r"(?<!\d)(?:0\d{2,3}[-—–\s]?\d{7,8}|1[3-9]\d{9})(?!\d)")
# 地址特征: 省/市/县/区/镇 + 路/街/道/号
_ADDR_PATTERN = re.compile(
    "((?:[\u4e00-\u9fa5]{2,6}(?:省|市|自治区|自治州|地区|盟))?"
    "[\u4e00-\u9fa5]{2,10}(?:市|县|区|镇|街道)"
    "[\u4e00-\u9fa5A-Za-z0-9]{2,25}(?:路|街|道|巷|号|小区|工业园|产业园|G[0-9]{1,3}|S[0-9]{1,3}|X[0-9]{1,3}|村))"
)

# 搜索结果中「单位名 + 电话/地址」关键词
_SEARCH_HINT = ("电话", "地址", "位于", "办公", "联系方式", "联系", "座机")

# 搜索引擎列表(轮换): 搜狗可直给电话, 360/百度可直给地址, Bing 兜底。
# 搜索引擎均有反爬风控, 故多引擎轮换 + 每次查询前 sleep。
_SEARCH_ENGINES = [
    {"name": "sogou", "url": "https://www.sogou.com/web?query={q}"},
    {"name": "so360", "url": "https://www.so.com/s?q={q}"},
    {"name": "bing", "url": "https://www.bing.com/search?mkt=zh-CN&q={q}"},
]
_SEARCH_SLEEP = 3  # 每次查询前延时(秒), 避免触发风控

# 域名可信度权重(DeepSeek 式可信度评分)
_DOMAIN_WEIGHT = {
    "gov.cn": 0.95, "org.cn": 0.85, "ac.cn": 0.9, "edu.cn": 0.85, "gov": 0.9,
    "baike.baidu.com": 0.8, "baike.com": 0.7, "zhihu.com": 0.7, "qichacha.com": 0.6,
    "tianyancha.com": 0.6, "aiqicha.baidu.com": 0.6, "qq.com": 0.5, "sohu.com": 0.4,
    "163.com": 0.4, "sina.com.cn": 0.4, "toutiao.com": 0.3,
}


def _domain_score(url: str) -> float:
    """URL 域名可信度: 政府/官方>百科>企业库>普通门户>自媒体。"""
    import urllib.parse
    host = (urllib.parse.urlparse(url).netloc or "").lower()
    if not host:
        return 0.3
    for dom, w in _DOMAIN_WEIGHT.items():
        if dom in host:
            return w
    if any(host.endswith(s) for s in (".gov.cn", ".gov")):
        return 0.95
    return 0.4


def _unit_core(unit_name: str) -> str:
    """提取单位核心名: 去掉「省/市/县/区/自治区」等行政区划前缀。

    搜索结果常用变体(如「汉源县自然资源和规划局」vs 单位名「汉源县自然资源局」,
    「山南市公路建设项目管理中心」vs「山南市公路建设管理中心」), 用核心名匹配更稳。
    """
    core = re.sub(r"^(?:[\u4e00-\u9fa5]{2,6}(?:省|市|县|区|自治区|自治州|地区|旗|州))", "", unit_name)
    return core.strip()


def _region_words(unit_name: str) -> list:
    """提取单位名的行政区划词(定日县/普兰县/汉源县/喀什市/山南市/成都等)。

    用于校验地址属于目标单位所在地(排除搜狗返回的「岗巴县」等同省他县地址)。
    取单位名前缀中 2~3 字的「xx县/xx市/xx区」; 无则返回空(不做校验)。
    """
    m = re.search(r"([\u4e00-\u9fa5]{2,3}(?:县|市|区|旗|州))", unit_name)
    return [m.group(1)] if m else []


def _clean_md(s: str) -> str:
    """清理 markdown 强调符号: 移除 `_xxx_` 下划线(搜索结果常用 _单位名_ 强调,
    会打断单位名匹配, 如 `_普兰县_ 住房和 _城乡_ 建设局`)。"""
    s = re.sub(r"_([^_\n]{1,30})_", r"\1", s)
    return s


def _parse_result_items(md: str) -> list:
    """从搜索引擎结果页 markdown 解析「结果条目」列表。

    每个条目: {title, url, snippet}。搜狗/360/Bing 结果页条目结构:
      ### 标题
      [标题](url) 或 描述文本(含链接与跳转中间页)
    解析策略: 按 `### ` 标题行切块, 块内找第一条 http 链接作 url, 其余文本作 snippet。
    """
    items = []
    md = _clean_md(md)
    parts = re.split(r"(?m)^(?=#{2,3}\s)", md)
    for part in parts:
        part = part.strip()
        if len(part) < 10:
            continue
        lines = part.split("\n")
        title = lines[0].lstrip("#").strip()
        if not title:
            continue
        # 收集块内 http 链接
        urls = re.findall(r"https?://[^\s\)\]\"']+", part)
        if not urls:
            continue
        url = urls[0]
        # 过滤导航/搜索框等无效链接
        if any(k in url for k in ("/s?", "/web?", "javascript:", "sogou.com/web", "so.com/s", "bing.com/search")):
            continue
        # snippet = 剩余文本(去链接行)
        snippet_lines = [l for l in lines[1:] if "http" not in l]
        snippet = " ".join(l.strip() for l in snippet_lines)[:400]
        items.append({"title": title, "url": url, "snippet": snippet})
    return items


def _extract_biz_card(md: str, unit_name: str) -> list:
    """提取搜索引擎结果页中的「工商信息聚合卡片」(360/搜狗常直接给爱企查/企查查摘要)。

    卡片特征: 含 法定代表人/注册资本/经营状态/统一社会信用代码 等工商词 + 单位名。
    360 用 `_成都市_ 双流区 _中医医院_` 下划线强调(非 ### 标题), 去下划线后含空格,
    单位名匹配必须用「去空格」版本, 否则整条卡片被误判无关而丢弃(法人补不到的直接原因)。
    返回规范化文本块列表(供 LLM 抽取 + 正则直提法人)。
    """
    core = _unit_core(unit_name)
    unit_nospace = unit_name.replace(" ", "")
    core_nospace = core.replace(" ", "")
    cards = []
    for block in re.split(r"(?m)^(?=#{2,3}\s)", md):
        block_ns = block.replace(" ", "").replace("\n", "")
        if unit_nospace not in block_ns and (len(core_nospace) < 4 or core_nospace not in block_ns):
            continue
        if not re.search(r"法定代表人|法人代表|注册资本|成立日期|经营状态|经营范围|统一社会信用代码|登记机关|企业类型",
                         block_ns):
            continue
        clean = _clean_md(block)
        clean = re.sub(r"\[[^\]]*\]\(https?://[^)]*\)", " ", clean)  # 去链接
        clean = re.sub(r"https?://\S+", " ", clean)
        clean = re.sub(r"[_*~`|]", " ", clean)
        clean = re.sub(r"\s{2,}", " ", clean).strip()
        if len(clean) > 40:
            cards.append(clean)
    return cards[:3]


def _score_item(item: dict, unit_name: str, core: str, idx: int) -> float:
    """结果条目可信度评分(DeepSeek 式): 域名权重 + 相关性 + 位置。

    相关性强弱: 标题含完整名 > 摘要含完整名 > 标题含核心名 > 摘要含核心名。
    """
    score = _domain_score(item.get("url") or "")
    title = item.get("title") or ""
    snippet = item.get("snippet") or ""
    if unit_name in title:
        score += 0.4
    elif unit_name in snippet:
        score += 0.3
    elif core and core in title:
        score += 0.2
    elif core and core in snippet:
        score += 0.15
    # 位置衰减: 越靠前越可信
    score += max(0, 0.2 - idx * 0.02)
    return round(score, 3)


def _related_blocks(md: str, unit_name: str, core: str) -> list:
    """把搜索结果按「结果条目」切块, 返回与单位相关的条目块。

    搜狗/百度结果页无空行分段, 按 `### 标题` 行切块(每条结果一个标题)。
    相关性判断: 块内含「完整单位名」优先(避免「凤凰县住建局」等同类单位误抓);
    没有完整名时才退化用核心名(兼容「自然资源和规划局」等变体)。
    匹配前清理下划线强调符号(`_普兰县_ 住房和 _城乡_ 建设局` → 普兰县住房和城乡建设局)。
    """
    md = _clean_md(md)
    # 按 ### 标题行切块(保留标题行)
    parts = re.split(r"(?m)^(?=#{2,3}\s)", md)
    blocks = [p.strip() for p in parts if len(p.strip()) >= 10]

    exact_blocks = []
    fuzzy_blocks = []
    for block in blocks:
        if unit_name in block:
            exact_blocks.append(block)
        elif core and core in block or (len(core) >= 5 and core[:5] in block):
            fuzzy_blocks.append(block)
    # 完整名命中优先; 否则核心名
    return exact_blocks or fuzzy_blocks


def _extract_phone_from_md(md: str, unit_name: str) -> Optional[str]:
    """从百度搜索 markdown 提取单位电话。

    在含单位名的段落块内找; 优先「电话/联系电话/公司电话:」显式标注的座机
    (0xx 开头), 次选块内出现的座机; 不取「联系人 1xx」经办人手机。
    """
    core = _unit_core(unit_name)
    candidates = []
    for block in _related_blocks(md, unit_name, core):
        # 电话: 0835-4222102 / 联系电话: 0892-8262350 / 公司电话: 028-87851159
        m = re.search(r"(?:电话|联系电话|公司电话|座机|办公电话|监督电话)[:：]?\s*([0-9][\d\-\s]{6,15})", block)
        if m:
            raw = m.group(1).strip()
            cand = _PHONE_PATTERN.search(raw)
            if cand:
                candidates.append(("explicit", cand.group(0)))
                continue
        # 块内含座机号(0xx 开头)
        for ph in _PHONE_PATTERN.findall(block):
            if ph.startswith("0"):
                candidates.append(("implicit", ph))
                break
    if not candidates:
        return None
    # 优先显式标注的座机, 且 0 开头的优先(单位座机而非经办人手机)
    for kind, ph in candidates:
        if kind == "explicit" and ph.startswith("0"):
            return ph
    for kind, ph in candidates:
        if kind == "explicit":
            return ph
    return candidates[0][1]


def _extract_addr_from_md(md: str, unit_name: str) -> Optional[str]:
    """从搜索结果 markdown 提取单位地址。在含单位名的条目块内找。"""
    core = _unit_core(unit_name)
    regions = _region_words(unit_name)

    def _clean_addr(t: str) -> str:
        t = re.sub(r"[_*~`]", "", t)
        t = re.sub(r"\s+(邮编|邮政编码|联系人|负责人|附近|更多|查看|办公时间|联系电话|电话)[：:]?[^\n]*$", "", t)
        return t.strip()

    def _pick_addr(candidates: list) -> Optional[str]:
        """从候选地址里挑: 含目标区划词, 且地址完整度最高(优先含路/街/道/号)。"""
        best = None
        for addr_text in candidates:
            addr_text = _clean_addr(addr_text)
            if not addr_text or len(addr_text) < 4:
                continue
            if regions and not any(rg in addr_text for rg in regions):
                continue
            am = _ADDR_PATTERN.search(addr_text)
            if not am:
                continue
            addr = am.group(1)
            # 优先保留含「路/街/道/号/村/G数字」的完整地址; 否则选最长
            score = len(addr)
            if any(k in addr for k in ("路", "街", "道", "号", "村", "小区", "工业园")):
                score += 50
            if best is None or score > best[0]:
                best = (score, addr)
        return best[1] if best else None

    for block in _related_blocks(md, unit_name, core):
        candidates = []
        # 括号地址: 单位名 (定日县上海中路1号老办公楼...)
        for pm in re.finditer(r"\(([^()\n]{6,60})\)", block):
            inner = pm.group(1)
            if any(k in inner for k in ("路", "街", "道", "号", "村", "县", "区", "镇")):
                candidates.append(inner)
        # 地址: ... / 单位地址:... / 办公地址:... / 位于...
        m = re.search(r"(?:地址|单位地址|办公地址|注册地址|位于)[:：]?\s*([^\n]{4,80})", block)
        if m:
            candidates.append(m.group(1).strip())
        # 腾讯地图等结果: 单独的「地址：xxx」行
        m2 = re.search(r"^地址[：:]\s*([^\n]{4,80})", block, re.MULTILINE)
        if m2:
            candidates.append(m2.group(1).strip().strip("_*~`"))
        addr = _pick_addr(candidates)
        if addr:
            return addr
    return None


def enrich_from_search(db, company) -> dict:
    """搜索引擎补全单位信息(免费, 较慢约 30~120s) — DeepSeek 式两段链路。

    Search 段: 查询重构(多组查询) × 多引擎轮换(搜狗→360→Bing) → 收集结果条目;
    可信度评分(域名权重 + 标题/摘要相关性 + 位置)排序。
    Extract 段: ① 正则从高可信条目 snippet 提取(快, 优先座机/完整地址);
               ② 正则未中时用 LLM 做相关性判断 + 结构化抽取(电话/地址/法人/邮箱/官网/简介)。
    原则: 只在相关条目提取, 不取招标代理/经办人手机, LLM 不编造, 查不到如实返回。
    返回 {"updated": [...], "source": str, "ok": bool, "message": str}
    """
    import time

    unit_name = company.name or company.code
    if not unit_name:
        return {"updated": [], "source": "search", "ok": False, "message": "单位名称为空"}
    core = _unit_core(unit_name)

    # ---- Search: 查询重构 × 多引擎收集条目 ----
    from app.services.search_llm import build_queries
    queries = build_queries(unit_name)  # 电话地址/法人/官网简介/中标公告 四组
    all_items = []
    biz_cards: list = []  # 工商信息聚合卡片(爱企查/企查查摘要, 含法定代表人等)
    tried = []
    for engine in _SEARCH_ENGINES:
        for q in queries:
            time.sleep(_SEARCH_SLEEP)
            try:
                result = crawl4ai_client.scrape(engine["url"].format(q=quote(q)))
            except Exception as e:  # noqa: BLE001
                logger.warning("[%s] 搜索失败 %s: %s", engine["name"], unit_name, e)
                continue
            md = result.get("markdown") or ""
            if any(k in md[:1500] for k in ("百度安全验证", "此验证码", "antispider", "访问过于频繁")):
                logger.warning("[%s] 触发反爬 %s", engine["name"], unit_name)
                tried.append(f"{engine['name']}(反爬)")
                break  # 该引擎已风控, 换下一引擎
            if not md or len(md) < 200:
                continue
            items = _parse_result_items(md)
            if items:
                all_items.extend(items)
                tried.append(engine["name"])
            # 工商聚合卡片(360/搜狗直接给爱企查摘要: 法定代表人/注册资本/经营范围等)
            try:
                biz_cards.extend(_extract_biz_card(md, unit_name))
            except Exception:  # noqa: BLE001
                pass
            # 命中足够的条目即停(不必每个引擎×查询都打)
            if len(all_items) >= 20:
                break
        if len(all_items) >= 20:
            break

    if not all_items:
        return {"updated": [], "source": "search", "ok": False,
                "message": f"搜索引擎均失败({', '.join(tried) or '无返回'})"}

    # 可信度评分排序(分数相同按原序, 避免 dict 比较), 取 top 12
    scored = sorted(
        ((_score_item(it, unit_name, core, i), i), it) for i, it in enumerate(all_items)
    )
    top_items = [it for _si, it in scored[-12:]][::-1]

    # ---- Extract 段 ①: 正则优先 ----
    all_md = "\n\n".join(
        f"### {it['title']}\n{it['snippet']}\n[{it['url']}]({it['url']})" for it in top_items
    )
    phone = _extract_phone_from_md(all_md, unit_name)
    addr = _extract_addr_from_md(all_md, unit_name)

    # ---- Extract 段 ②: 正文抓取 + LLM 结构化抽取(DeepSeek 式) ----
    # 目标: 补齐工商字段(法人/注册资本/登记机关/经营范围/成立日期/经营状态等),
    # 这些在 snippet 里通常没有, 需抓取高可信条目的正文。
    llm_result = {}
    try:
        from app.services.search_llm import extract_info
        # 取前 3 个高可信、含单位名的条目抓正文
        rel_items = [
            it for it in top_items[:5]
            if unit_name in (it["title"] + it["snippet"])
            or (core and core in (it["title"] + it["snippet"]))
        ][:3]
        bodies = []
        # 优先抓工商信息类域名(爱企查/企查查/天眼查), 其后普通结果
        biz_domains = ("aiqicha", "qichacha", "tianyancha", "qcc.com", "qixin")
        ordered = sorted(
            rel_items,
            key=lambda it: (0 if any(d in (it.get("url") or "") for d in biz_domains) else 1),
        )
        for it in ordered[:4]:
            url = (it.get("url") or "").strip()
            if not url:
                continue
            # 跳过已知导航/广告域名
            if any(skip in url for skip in ("/s?", "javascript:", "sogou.com", "so.com", "bing.com")):
                continue
            try:
                rr = crawl4ai_client.scrape(url)
                body_md = rr.get("markdown") or ""
                # 截取与单位相关的一段正文(去导航)
                if body_md and len(body_md) > 300:
                    bodies.append(f"[{it['title']}] {body_md[:2500]}")
            except Exception as e:  # noqa: BLE001
                logger.warning("[search] 抓正文失败 %s: %s", url, e)
        # 工商卡片并入 feed: 正文优先, 其次工商卡片(含法人/注册资本等), 最后 snippet 兜底
        card_text = "\n\n".join(biz_cards[:3])
        if bodies:
            feed = "\n\n".join(bodies[:2] + ([card_text] if card_text else []))
        elif card_text:
            feed = card_text
        else:
            feed = "\n\n".join(f"[{it['title']}]\n{it['snippet']}" for it in rel_items[:4])
        if feed:
            llm_result = extract_info(unit_name, feed)
            if not phone and llm_result.get("contact_phone"):
                phone = llm_result["contact_phone"]
            if not phone and llm_result.get("contact"):
                phone = llm_result["contact"]
            if not addr and llm_result.get("address"):
                addr = llm_result["address"]
    except Exception as e:  # noqa: BLE001
        logger.warning("[search] LLM 抽取失败 %s: %s", unit_name, e)

    # 法定代表人: 正则直提优先(确定性高), LLM 兜底。
    # (修复: 曾以 LLM 结果优先, 工商卡片文本干扰导致把「注册资本」抽成法人)
    _BAD_LEGAL = ("注册资本", "成立日期", "经营状态", "经营范围", "统一社会信用", "登记机关",
                  "企业类型", "法定代表人", "法人代表", "单位", "机构", "营业")
    legal_rep = None
    for blk in biz_cards + [f"{it['title']}\n{it['snippet']}" for it in top_items[:8]]:
        m = _LEGAL_RE.search(blk)
        if m and m.group(1).strip("·") not in _BAD_LEGAL:
            legal_rep = m.group(1).strip("·")
            break
    if not legal_rep and llm_result.get("legal_rep") and llm_result["legal_rep"] not in _BAD_LEGAL:
        legal_rep = llm_result["legal_rep"]

    if not phone and not addr and not legal_rep and not llm_result:
        return {"updated": [], "source": "search", "ok": False,
                "message": f"搜索到该单位但未提取到座机/地址/法人({', '.join(tried)})"}

    # ---- 写入(只填空字段) ----
    updated = []
    ext = dict(company.ext_attrs or {})
    if phone:
        # 电话同时写 contact(甲方联系方式) 与 contact_phone(联系电话) 两个字段
        if _is_blank(ext.get("contact")):
            ext["contact"] = phone
            updated.append("ext:contact")
        if _is_blank(ext.get("contact_phone")):
            ext["contact_phone"] = phone
            updated.append("ext:contact_phone")
    if legal_rep and _is_blank(ext.get("legal_rep")):
        ext["legal_rep"] = legal_rep
        updated.append("ext:legal_rep")
    if addr and _is_blank(company.address):
        company.address = addr
        updated.append("address")
    # 先把 phone/addr 落回对象, 再并入 LLM 其余字段(避免 merge 读到旧 ext 覆盖)
    if updated:
        company.ext_attrs = ext
    # LLM 补充的法人/注册资本/登记机关/经营范围/联系人/传真/邮编/办公时间等一并并入
    # (只填空字段; 新字段自动动态创建并保存)
    created_fields: list = []
    if llm_result:
        try:
            from app.services.search_llm import merge_llm_to_company
            llm_updates, created_fields = merge_llm_to_company(db, company, llm_result)
            for u in llm_updates:
                if u not in updated:
                    updated.append(u)
        except Exception:  # noqa: BLE001
            pass

    if not updated:
        return {"updated": [], "source": "search", "ok": True,
                "message": "搜索提取到电话/地址, 但已有字段未覆盖"}
    result = {"updated": updated, "source": "search", "ok": True, "message": "ok"}
    if created_fields:
        result["created_fields"] = created_fields
    return result


def _clue_meta(clue: WebClue) -> dict:
    if isinstance(clue.meta, dict):
        return clue.meta
    if isinstance(clue.meta, str):
        try:
            return json.loads(clue.meta)
        except Exception:
            return {}
    return {}


def _name_match(unit_name: str, target: str) -> bool:
    """单位名匹配: 完全一致或互为包含(去空白/省市前缀干扰)。"""
    if not target:
        return False
    a = unit_name.replace(" ", "")
    b = target.replace(" ", "")
    return a == b or (len(a) >= 4 and (a in b or b in a))


def enrich_from_clue_library(db: Session, company) -> dict:
    """从 web_clue 公告库匹配采购人信息(免费、即时)。

    匹配规则: 公告 meta.purchaser 与单位名完全一致或包含;
    优先取最新一条, 提取 purchaserLinkPhone → ext.contact, purchaserAddr → address。
    返回 {"updated": [...], "source": "clue", "ok": bool, "message": str}
    """
    unit_name = company.name or company.code
    clues = db.execute(
        select(WebClue).where(WebClue.is_deleted == False).order_by(WebClue.fetched_at.desc()).limit(500)
    ).scalars().all()

    best_phone = None
    best_addr = None
    best_win_amount = None
    best_supplier = None
    for clue in clues:
        meta = _clue_meta(clue)
        purchaser = meta.get("purchaser") or ""
        if _name_match(unit_name, purchaser):
            phone = (meta.get("purchaserLinkPhone") or "").strip()
            addr = (meta.get("purchaserAddr") or "").strip()
            if not best_phone and phone:
                best_phone = phone
            if not best_addr and addr:
                best_addr = addr
            if best_phone and best_addr:
                break
            continue
        # 中标供应商匹配: 采购人未命中时, 尝试匹配 procurement_result 里的中标供应商
        for w in meta.get("procurement_result") or []:
            supplier = (w.get("supplier") or "").strip()
            if not _name_match(unit_name, supplier):
                continue
            if not best_addr:
                best_addr = (w.get("address") or "").strip()
            if not best_win_amount:
                best_win_amount = (w.get("amount") or "").strip()
            best_supplier = supplier
            if best_addr and best_win_amount:
                break
        if best_addr and best_win_amount:
            break

    if not best_phone and not best_addr and not best_win_amount:
        return {"updated": [], "source": "clue", "ok": False,
                "message": "公告库中未找到该单位作为采购人的公开联系方式"}

    updated = []
    ext = dict(company.ext_attrs or {})
    if best_phone and _is_blank(ext.get("contact")):
        ext["contact"] = best_phone
        updated.append("ext:contact")
    if best_addr and _is_blank(company.address):
        company.address = best_addr
        updated.append("address")
    if best_win_amount and _is_blank(ext.get("win_amount")):
        ext["win_amount"] = best_win_amount
        updated.append("ext:win_amount")
    if best_supplier and _is_blank(ext.get("supplier_role")):
        ext["supplier_role"] = best_supplier
        updated.append("ext:supplier_role")
    if updated:
        company.ext_attrs = ext

    if not updated:
        return {"updated": [], "source": "clue", "ok": True,
                "message": "公告库匹配到采购人/供应商信息, 但已有字段未覆盖"}
    return {"updated": updated, "source": "clue", "ok": True, "message": "ok"}


def enrich_from_ccgp(company) -> dict:
    """主动检索四川政府采购网补全(免费、权威, 较慢约 30~90s)。

    用单位名作为关键词 query_crawl 检索公告, 从返回 meta 提取
    purchaserLinkPhone → ext.contact, purchaserAddr → address。
    返回 {"updated": [...], "source": "ccgp", "ok": bool, "message": str}
    """
    unit_name = company.name or company.code
    try:
        result = crawl4ai_client.query_crawl(
            _CCGP_URL,
            query_config=_CCGP_QUERY_CONFIG,
            max_pages=1,
            search_keywords=unit_name,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("[ccgp] 检索失败 %s: %s", unit_name, e)
        return {"updated": [], "source": "ccgp", "ok": False, "message": f"检索失败: {e}"}

    data = result.get("data") or []
    if not data:
        return {"updated": [], "source": "ccgp", "ok": False,
                "message": "政府采购网未检索到该单位公告(或 OCR 验证码失败)"}

    best_phone = None
    best_addr = None
    for item in data:
        meta = item.get("meta") or {}
        purchaser = meta.get("purchaser") or ""
        if purchaser and not _name_match(unit_name, purchaser):
            continue
        phone = (meta.get("purchaserLinkPhone") or "").strip()
        addr = (meta.get("purchaserAddr") or "").strip()
        if not best_phone and phone:
            best_phone = phone
        if not best_addr and addr:
            best_addr = addr
        if best_phone and best_addr:
            break

    if not best_phone and not best_addr:
        return {"updated": [], "source": "ccgp", "ok": False,
                "message": f"检索到 {len(data)} 条公告但未提取到采购人电话/地址"}

    updated = []
    ext = dict(company.ext_attrs or {})
    if best_phone and _is_blank(ext.get("contact")):
        ext["contact"] = best_phone
        updated.append("ext:contact")
    if best_addr and _is_blank(company.address):
        company.address = best_addr
        updated.append("address")
    if updated:
        company.ext_attrs = ext

    if not updated:
        return {"updated": [], "source": "ccgp", "ok": True,
                "message": "检索到采购人信息, 但已有字段未覆盖"}
    return {"updated": updated, "source": "ccgp", "ok": True, "message": "ok"}


def enrich_from_ccgp_winner(company) -> dict:
    """从中标(成交)结果公告补全供应商信息(免费、权威, 较慢约 30~90s)。

    用单位名作为关键词 query_crawl 检索中标结果公告, 从公告 meta.procurement_result
    匹配中标供应商, 提取 supplier address → address, amount → ext.win_amount,
    supplier_name(若与单位名不同) → ext.supplier_role 标注。
    返回 {"updated": [...], "source": "ccgp_winner", "ok": bool, "message": str}
    """
    unit_name = company.name or company.code
    try:
        result = crawl4ai_client.query_crawl(
            _CCGP_URL,
            query_config=_CCGP_QUERY_CONFIG,
            max_pages=1,
            search_keywords=unit_name,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("[ccgp_winner] 检索失败 %s: %s", unit_name, e)
        return {"updated": [], "source": "ccgp_winner", "ok": False, "message": f"检索失败: {e}"}

    data = result.get("data") or []
    if not data:
        return {"updated": [], "source": "ccgp_winner", "ok": False,
                "message": "政府采购网未检索到该单位公告(或 OCR 验证码失败)"}

    best_addr = None
    best_amount = None
    best_supplier = None
    for item in data:
        meta = item.get("meta") or {}
        for w in meta.get("procurement_result") or []:
            supplier = (w.get("supplier") or "").strip()
            if not _name_match(unit_name, supplier):
                continue
            if not best_addr:
                best_addr = (w.get("address") or "").strip()
            if not best_amount:
                best_amount = (w.get("amount") or "").strip()
            best_supplier = supplier
            if best_addr and best_amount:
                break
        if best_addr and best_amount:
            break

    if not best_addr and not best_amount:
        return {"updated": [], "source": "ccgp_winner", "ok": False,
                "message": f"检索到 {len(data)} 条公告但未匹配到该单位作为中标供应商"}

    updated = []
    ext = dict(company.ext_attrs or {})
    if best_addr and _is_blank(company.address):
        company.address = best_addr
        updated.append("address")
    if best_amount and _is_blank(ext.get("win_amount")):
        ext["win_amount"] = best_amount
        updated.append("ext:win_amount")
    if best_supplier and _is_blank(ext.get("supplier_role")):
        ext["supplier_role"] = best_supplier
        updated.append("ext:supplier_role")
    if updated:
        company.ext_attrs = ext

    if not updated:
        return {"updated": [], "source": "ccgp_winner", "ok": True,
                "message": "匹配到中标供应商信息, 但已有字段未覆盖"}
    return {"updated": updated, "source": "ccgp_winner", "ok": True, "message": "ok"}


def enrich_company_free(db: Session, company) -> dict:
    """组合免费渠道补全(多渠道合并, 字段更全):
    公告库匹配(即时) → 多引擎搜索+LLM 抽取(工商字段) → 四川政采网(电话/地址权威兜底)。

    与旧版(第一个 ok 渠道即 return)不同: 所有渠道依次执行并**合并**结果, 字段更全
    (修复: 旧版公告库匹配到 contact/address 就停, 不再跑最全的 search+LLM, 字段明显偏少)。
    原则: 只填空字段、不覆盖已有信息; 查不到如实返回。
    返回 {"updated": [...], "source": "clue+search+ccgp", "ok": bool, "message": str}
    """
    updated: list = []
    sources: list = []
    created_fields: list = []
    msgs: list = []

    # 1) 公告库匹配(即时, 零网络)
    r1 = enrich_from_clue_library(db, company)
    if r1.get("updated"):
        updated.extend(r1["updated"])
        sources.append("clue")
    elif r1.get("ok"):
        msgs.append(r1.get("message", ""))

    # 2) 多引擎搜索 + LLM 抽取(最全: 电话/地址 + 法人/注册资本/经营范围/成立日期/经营状态/登记机关等)
    r2 = enrich_from_search(db, company)
    if r2.get("updated"):
        updated.extend(r2["updated"])
        sources.append("search")
        if r2.get("created_fields"):
            created_fields.extend(r2["created_fields"])
    elif r2.get("ok"):
        msgs.append(r2.get("message", ""))

    # 3) 电话/地址权威兜底: search 已补到完整电话+地址则跳过(政采网检索较慢)
    def _has_addr():
        return any(u == "address" for u in updated)

    def _has_contact():
        return any(u.startswith("ext:contact") for u in updated)

    if not (_has_addr() and _has_contact()):
        r3 = enrich_from_ccgp(company)
        if r3.get("updated"):
            updated.extend(r3["updated"])
            sources.append("ccgp")
        elif r3.get("ok"):
            msgs.append(r3.get("message", ""))
        if not _has_addr():
            r4 = enrich_from_ccgp_winner(company)
            if r4.get("updated"):
                updated.extend(r4["updated"])
                sources.append("ccgp_winner")
            elif r4.get("ok"):
                msgs.append(r4.get("message", ""))

    # 去重保序
    seen, upd_dedup = set(), []
    for u in updated:
        if u not in seen:
            seen.add(u)
            upd_dedup.append(u)

    if not upd_dedup:
        return {"updated": [], "source": "+".join(sources) or "mixed", "ok": False,
                "message": "; ".join(m for m in msgs) or "所有免费渠道均未补到新字段"}
    result = {"updated": upd_dedup, "source": "+".join(sources) or "mixed", "ok": True, "message": "ok"}
    if created_fields:
        result["created_fields"] = created_fields
    return result
