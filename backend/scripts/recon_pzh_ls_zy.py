"""探测攀枝花/凉山/资阳 的交易信息列表页 URL。"""
import re, ssl, urllib.request
ssl._create_default_https_context = ssl._create_unverified_context

def fetch(url, timeout=30, maxbytes=500000):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.geturl(), r.read(maxbytes).decode("utf-8", "replace")
    except Exception as e:
        return None, "", f"ERR:{e}"

def show(sid, url, raw=False):
    st, final, html = fetch(url)
    print(f"\n===== [{sid}] {url} -> {st} final={final[:80]}")
    if not isinstance(html, str):
        return
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if m:
        print("  title:", m.group(1).strip()[:70])
    if raw:
        print("  HTML 前 900 字符:")
        print("   ", re.sub(r"\s+", " ", html[:900])[:900])
        return
    links = re.findall(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html, re.S | re.I)
    seen, n = set(), 0
    for href, txt in links:
        txt = re.sub(r"<[^>]+>", "", txt).strip(); txt = re.sub(r"\s+", "", txt)
        if not txt or len(txt) > 18 or href.startswith(("javascript", "#", "mailto")):
            continue
        if href in seen:
            continue
        seen.add(href); n += 1
        if n > 30:
            break
        print(f"  {txt:18} -> {href[:95]}")

show(77, "http://ggzy.panzhihua.gov.cn/toJyxxIndex")
# 凉山: 试常见交易信息路径
for p in ("/jyxx/", "/jyxx/index.html", "/jyxxinfo/", "/tradeinfo/"):
    show(83, "https://ggzyjy.lsz.gov.cn" + p)
# 资阳: 看原始 HTML 判断渲染方式
show(107, "https://zyzwjy.cn/", raw=True)
