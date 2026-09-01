"""网页线索解析/抓取工具(纯函数, 无路由/无共享状态)。

从 api/v1/web_clues.py 拆出: 日期解析、时间窗过滤、政府采购网结果解析、
静态页抓取(编码自动识别)。供 web_clues 路由与抓取编排复用。
"""
import datetime
import logging
import re

import httpx

logger = logging.getLogger("web_clues")


def _parse_dt(s) -> datetime.datetime:
    """解析日期字符串(兼容 'YYYY-MM-DD HH:MM:SS' 与 ISO)。失败返回 None。"""
    if not s:
        return None
    s = str(s).strip().replace("Z", "+00:00").replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y年%m月%d日 %H时%M分"):
        try:
            return datetime.datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    try:
        return datetime.datetime.fromisoformat(s)
    except ValueError:
        return None


def _time_window_reject(meta) -> str:
    """按公告截止时间窗口过滤。返回拒绝原因字符串, 通过则返回 None。

    规则: expire_time(截止时间)存在且已过期 -> 拒绝; 其他情况通过。
    """
    if not meta or not isinstance(meta, dict):
        return None
    now = datetime.datetime.now()
    expire = _parse_dt(meta.get("expire_time") or meta.get("end_time"))
    if expire and expire < now:
        return f"公告已截止(截止时间 {expire:%Y-%m-%d %H:%M})"
    return None


def _ccgp_procurement_result(text: str) -> list:
    """从中国政府采购网中标公告详情 HTML 提取「三、采购结果」表格(供应商/地址/金额)。

    详情页为静态 HTML, 采购结果在 supplier 容器内的 <table>, 列:
      供应商名称 | 供应商地址 | 中标（成交）金额 | 评审总得分
    兼容 markdown pipe / tab 分隔的纯文本输入(内部工具复用)。
    返回 [ {supplier, address, amount} ]。
    """
    import re as _re
    if not text:
        return []
    # 0) 文本列表格式: 供应商名称：X 供应商地址：Y 中标（成交）金额：Z (无表格)
    if _re.search(r"供应商名称[：:]", text) and "供应商名称：" in text.replace("&nbsp;", " "):
        plain = _re.sub(r"<[^>]+>", " ", text)
        plain = _re.sub(r"&nbsp;", " ", plain)
        plain = _re.sub(r"\s+", " ", plain)
        m_name = _re.search(r"供应商名称[：:\s]*([^\s]{2,})", plain)
        if m_name:
            supplier = m_name.group(1).strip()
            m_addr = _re.search(r"供应商地址[：:\s]*([^\s]{4,})", plain)
            m_amt = _re.search(r"金额[^0-9]{0,15}?([\d,]+\.\d+)", plain)
            if m_name and supplier and not _re.fullmatch(r"[\d\s]+", supplier):
                return [{
                    "supplier": supplier[:120],
                    "address": (m_addr.group(1) if m_addr else "")[:200],
                    "amount": ((m_amt.group(1) if m_amt else "") + "元")[:80],
                }]
    # 1) 若为 HTML: 提取 supplier 容器内的表格
    if "<table" in text or "<td" in text:
        seg = text
        # 定位「三、采购结果」/「中标（成交）信息」, 从其后开始; 找不到则退回「采购包」关键词
        i = seg.find("三、采购结果")
        if i < 0:
            i = seg.find("中标（成交）信息")
        if i < 0:
            i = seg.find("中标/成交结果信息")
        if i < 0:
            i = seg.find("采购结果")
        if i >= 0:
            seg = seg[i:]
        else:
            # 无任何标题: 找含「供应商名称」表头的 table 起点
            i = seg.find("供应商名称")
            if i >= 0:
                seg = seg[max(0, i - 300):]
            else:
                i = seg.find("采购包")
                if i >= 0:
                    seg = seg[i:]
        # 找第一个 table(供应商结果表)
        ti = seg.find("<table")
        if ti < 0:
            return []
        ti2 = seg.find("</table>", ti)
        if ti2 < 0:
            return []
        table_html = seg[ti:ti2 + len("</table>")]
        rows = []
        for rm in _re.finditer(r"<tr[^>]*>([\s\S]*?)</tr>", table_html):
            cells = [_re.sub(r"<[^>]+>", "", c).strip()
                     for c in _re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", rm.group(1))]
            if not cells:
                continue
            cells = [c for c in cells if c]
            # 序号列: 首列纯数字(如「1」)视为行号, 供应商从第二列开始
            if cells and _re.fullmatch(r"\d{1,3}", cells[0].strip()) and len(cells) >= 4:
                cells = cells[1:]
            rows.append(cells)
        result = []
        header_seen = False
        for cells in rows:
            if any(("供应商名称" in c or "供应商地址" in c) for c in cells):
                header_seen = True
                continue
            if not header_seen:
                continue
            if len(cells) < 3:
                continue
            supplier = cells[0]
            address = cells[1]
            amount_cell = ""
            for c in cells[2:]:
                if "元" in c or _re.search(r"\d", c):
                    amount_cell = c
                    break
            if not amount_cell and len(cells) > 3:
                amount_cell = cells[2]
            amount_cell = amount_cell.replace(",", "")
            if supplier and not _re.fullmatch(r"[\d\s]+", supplier) and "供应商名称" not in supplier:
                result.append({"supplier": supplier[:120], "address": address[:200], "amount": amount_cell[:80]})
        if result:
            return result
        # HTML 表格未解析出, 回退到纯文本逻辑
        text = _re.sub(r"<[^>]+>", "\n", text)

    # 2) 纯文本: 定位「三、采购结果」段(tab 分隔或 markdown pipe)
    start = text.find("三、采购结果")
    if start < 0:
        start = text.find("中标（成交）供应商")
    if start < 0:
        start = text.find("采购结果")
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

    def _row(cells: list):
        if not cells:
            return None
        if any(c.strip().replace("-", "").replace("+", "") == "" for c in cells):
            return None
        cleaned = [c for c in cells if c.strip()]
        if not cleaned:
            return None
        if any(("供应商名称" in c or "供应商地址" in c) for c in cleaned):
            return {"_header": True}
        if all(_re.fullmatch(r"[-:\s]*", c) for c in cleaned):
            return None
        if len(cleaned) < 3:
            return None
        supplier = cleaned[0]
        address = cleaned[1]
        amount_cell = ""
        for c in cleaned[2:]:
            if "元" in c or _re.search(r"\d", c):
                amount_cell = c
                break
        if not amount_cell and len(cleaned) > 3:
            amount_cell = cleaned[2]
        amount_cell = amount_cell.replace(",", "")
        if supplier and not _re.fullmatch(r"[\d\s]+", supplier) and "供应商名称" not in supplier:
            return {"supplier": supplier[:120], "address": address[:200], "amount": amount_cell[:80]}
        return None

    for line in block.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            r = _row(cells)
        elif "\t" in line:
            cells = [c.strip() for c in line.split("\t")]
            r = _row(cells)
        else:
            continue
        if r is None:
            continue
        if r.get("_header"):
            header_seen = True
            continue
        if not header_seen:
            continue
        result.append(r)
        header_seen = False
    return result


def _ccgp_fetch_html(url: str, timeout: float = 30.0) -> str:
    """抓取中国政府采购网静态页, 自动处理 GB2312/GBK 编码。

    注意: 必须带 UA + Referer, 缺失时源站直接返回 403(实测)。
    """
    try:
        resp = httpx.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
            "Referer": "https://www.ccgp.gov.cn/",
        }, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        raw = resp.content
        for enc in ("utf-8", "gb18030", "gbk"):
            try:
                return raw.decode(enc)
            except Exception:  # noqa: BLE001
                continue
        return raw.decode("gb18030", errors="replace")
    except Exception as e:  # noqa: BLE001
        logger.warning("[ccgp] fetch %s error: %s", url, e)
        return ""


# 附件区 DOM(实测 标讯 383 中国政府采购网全国站):
#   <p class='fjxx'>附件信息：</p>
#   <ul class="fjxx" ...>
#     <li>
#       <p style="display:inline-block"><a href="https://...doc" ignore=1>名称.doc</a></p>
#       <p style="display:inline-block;margin-left:20px">720.5K</p>
#     </li>
#   </ul>
_CCGP_ATT_BLOCK_RE = re.compile(r"<ul[^>]*class=[\"']?fjxx[\"']?[^>]*>([\s\S]*?)</ul>", re.I)
_CCGP_ATT_LI_RE = re.compile(r"<li[^>]*>([\s\S]*?)</li>", re.I)
_CCGP_ATT_LINK_RE = re.compile(r"<a[^>]+href=[\"']?([^\"'\s>]+)[\"']?[^>]*>([\s\S]*?)</a>", re.I)
_CCGP_ATT_SIZE_RE = re.compile(r"([\d.]+\s*[KMG]B?)", re.I)
# 附件直链常见形态: 政务 OSS / download / 常见文档后缀
_CCGP_ATT_URL_RE = re.compile(
    r"https?://[^\"'\s>]+?\.(?:zip|rar|7z|pdf|doc|docx|xls|xlsx|wps|et)(?:\?[^\"'\s>]*)?", re.I
)


def _ccgp_attachments(html: str) -> list:
    """从中国政府采购网详情页提取「附件信息」区的附件(名称/下载链接/大小)。

    实测: 采集器此前只把正文转成文本, 附件区的 <a href> 被整段丢弃,
    导致大量标讯"正文里写着有附件、接口里 attachments 却是空数组"。

    抓不到链接时返回空列表, 不臆造、不用正文线索冒充。
    """
    if not html:
        return []
    out: list = []
    seen: set = set()
    for block in _CCGP_ATT_BLOCK_RE.findall(html):
        for li in _CCGP_ATT_LI_RE.findall(block):
            m = _CCGP_ATT_LINK_RE.search(li)
            if not m:
                continue
            url = m.group(1).strip()
            name = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            if not url or not name:
                continue
            # 只保留真正的文档链接, 过滤站内导航/js
            if not _CCGP_ATT_URL_RE.search(url) and "oss-" not in url and "download" not in url.lower():
                continue
            if url in seen:
                continue
            seen.add(url)
            size_m = _CCGP_ATT_SIZE_RE.search(re.sub(r"<a[\s\S]*?</a>", "", li))
            out.append({
                "name": name[:200],
                "url": url,
                "size": size_m.group(1) if size_m else None,
            })
    return out


def ccgp_detail_extras(url: str, timeout: float = 30.0) -> dict:
    """抓取 ccgp 详情页并返回可补录的结构化补充字段(当前仅附件)。

    后续采集流程直接调用, 保证新入库数据带附件链接。
    """
    html = _ccgp_fetch_html(url, timeout=timeout)
    if not html:
        return {"attachments": []}
    return {"attachments": _ccgp_attachments(html)}
