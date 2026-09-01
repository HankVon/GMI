"""1) 拉省平台全部市州官方 URL   2) 探测凉山平台列表页   3) 确认资阳官方 URL"""
import re, ssl, urllib.request
ssl._create_default_https_context = ssl._create_unverified_context

def fetch(url, timeout=30, maxbytes=600000):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.geturl(), r.read(maxbytes).decode("utf-8", "replace")
    except Exception as e:
        return None, "", f"ERR:{e}"

print("##### 省平台: 全部市州官方 URL #####")
st, final, html = fetch("https://ggzyjy.sc.gov.cn/")
cities = re.findall(r"<option[^>]*title=\"([^\"]+)\"[^>]*value=\"([^\"]+)\"", html)
if not cities:
    cities = re.findall(r"<option[^>]*value=\"(https?://[^\"]+)\"[^>]*>([^<]+)</option>", html)
    cities = [(b.strip(), a) for a, b in cities]
seen = set()
for name, url in cities:
    if name in seen:
        continue
    seen.add(name)
    print(f"  {name:8} -> {url}")

print("\n\n##### 凉山平台列表页探测 #####")
for u in ("http://www.lszggzyjy.com.cn/TPFront", "http://www.lszggzyjy.com.cn/TPFront/"):
    st, final, html = fetch(u)
    print(f"\n[{u}] status={st} final={final[:80]}")
    if not isinstance(html, str):
        continue
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if m:
        print("  title:", m.group(1).strip()[:70])
    links = re.findall(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html, re.S | re.I)
    seen2, n = set(), 0
    for href, txt in links:
        txt = re.sub(r"<[^>]+>", "", txt).strip(); txt = re.sub(r"\s+", "", txt)
        if not txt or len(txt) > 18 or href.startswith(("javascript", "#", "mailto")):
            continue
        if href in seen2:
            continue
        seen2.add(href); n += 1
        if n > 28:
            break
        print(f"  {txt:18} -> {href[:95]}")
    if st == 200:
        break
