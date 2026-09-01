"""批量探活若干数据源 URL: 区分 域名失效(DEAD) 与 可访问(ALIVE/HTTP码)。
在后端容器内运行: docker exec ssm-backend python check_urls.py
"""
import httpx
from app.database import SessionLocal
from app.models.web_source import WebSource

ids = [75,77,79,80,81,83,84,85,103,104,106,109,110,
       88,89,90,91,92,93,
       114,115,116,117,118,119,120,121,122,123,124,125,
       31,36,105,107,108]

db = SessionLocal()
rows = db.query(WebSource.id, WebSource.url, WebSource.name).filter(WebSource.id.in_(ids)).all()
db.close()

for sid, url, name in rows:
    try:
        r = httpx.get(url, follow_redirects=True, timeout=18,
                      headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        print(f"ALIVE {r.status_code}  id={sid}  {name}  | {url} -> {str(r.url)}")
    except Exception as e:
        print(f"DEAD    id={sid}  {name}  | {url}  | {type(e).__name__}: {str(e)[:90]}")
