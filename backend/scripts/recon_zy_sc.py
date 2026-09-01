"""1) 资阳 Vue SPA: 从 JS 找接口/列表路由  2) 省平台 ggzyjy.sc.gov.cn: 找各市州城市码(含凉山)"""
import re, ssl, urllib.request
ssl._create_default_https_context = ssl._create_unverified_context

def fetch(url, timeout=30, maxbytes=900000):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(maxbytes).decode("utf-8", "replace")
    except Exception as e:
        return None, f"ERR:{e}"

print("##### 资阳 SPA: JS 接口/路由线索 #####")
for js in ("static/js/app.68dbe281.js", "static/js/main.e854a157.js"):
    st, txt = fetch("https://zyzwjy.cn/" + js)
    if not isinstance(txt, str):
        print(f"  {js}: {txt}"); continue
    print(f"\n  --- {js} ({len(txt)} 字符) ---")
    pats = (r"https?://[^\"'\s,)]{6,80}", r"[\"'/]api[^\"'\s,)]{0,60}",
            r"[\"'/](jyxx|notice|zbgg|trade|ggzy)[^\"'\s,)]{0,50}")
    for p in pats:
        hits = set(m.group(0) for m in re.finditer(p, txt, re.I))
        cands = [h for h in hits if not h.startswith(("http://www.w3", "https://www.w3"))][:12]
        if cands:
            print(f"   [{p[:24]}] {cands}")

print("\n\n##### 省平台 ggzyjy.sc.gov.cn: 市州城市码 #####")
st, html = fetch("https://ggzyjy.sc.gov.cn/")
print("status:", st)
if isinstance(html, str):
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if m:
        print("title:", m.group(1).strip()[:70])
    # 找 /jyxx/六位数字 形式的城市码链接, 及其附近城市名
    codes = {}
    for mm in re.finditer(r"/jyxx/(\d{6})", html):
        codes.setdefault(mm.group(1), 0)
        codes[mm.group(1)] += 1
    print("  城市码:", dict(list(codes.items())[:25]))
    # 找城市名与其链接
    for txt in ("凉山", "攀枝花", "甘孜", "阿坝"):
        for mm in re.finditer(txt, html):
            s = max(0, mm.start()-160); e = min(len(html), mm.end()+80)
            seg = re.sub(r"\s+", " ", html[s:e])
            print(f"  [{txt}] ...{seg}...")
            break
