"""资阳: 试官方站根域名 + 用浏览器渲染 zyzwjy.cn 看公告列表链接"""
import re, ssl, urllib.request
ssl._create_default_https_context = ssl._create_unverified_context

def fetch(url, timeout=25, maxbytes=600000):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.geturl(), r.read(maxbytes).decode("utf-8", "replace")
    except Exception as e:
        return None, "", f"ERR:{e}"

for u in ("https://ggzyjyzx.ziyang.gov.cn/", "http://ggzyjyzx.ziyang.gov.cn/",
          "https://ggzyjyzx.ziyang.gov.cn/oldHome/index.html"):
    st, final, html = fetch(u)
    print(f"[{u}] status={st} final={final[:80]}")
    if isinstance(html, str):
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        print("   title:", (m.group(1).strip()[:70] if m else ""))
        links = re.findall(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html, re.S | re.I)
        seen, n = set(), 0
        for href, txt in links:
            txt = re.sub(r"<[^>]+>", "", txt).strip(); txt = re.sub(r"\s+", "", txt)
            if not txt or len(txt) > 18 or href.startswith(("javascript", "#", "mailto")):
                continue
            if href in seen:
                continue
            seen.add(href); n += 1
            if n > 22:
                break
            print(f"   {txt:18} -> {href[:90]}")
        break

print("\n##### 浏览器渲染 zyzwjy.cn #####")
try:
    from app.services.crawl4ai_client import crawl4ai_client
    r = crawl4ai_client.scrape("https://zyzwjy.cn/", page_timeout=90000, extra_delay=3.0)
    md = r.get("markdown") or ""
    print("title:", (r.get("title") or "")[:60], "| md 长度:", len(md))
    for txt, href in re.findall(r"\[([^\]]+)\]\((https?://[^\s)]+|/[^\s)]*)\)", md)[:25]:
        print(f"  {txt.strip()[:20]:20} -> {href[:90]}")
except Exception as e:
    print("  render ERROR:", str(e)[:200])
