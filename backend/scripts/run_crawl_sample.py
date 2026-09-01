"""抽样抓取: 对三省代表性数据源各抓一份, 随后抽样 web_clue 看入库质量。
在后端容器内运行: docker exec -i ssm-backend python run_crawl_sample.py
"""
from app.database import SessionLocal
from app.models.web_source import WebSource
from app.models.web_clue import WebClue
from app.api.v1 import web_clues as wc

SAMPLE_IDS = [57, 74, 60, 65, 37, 87]  # 四川(省/成都)、西藏(省/拉萨)、新疆(省)、自然资源部探矿权

db = SessionLocal()
try:
    for sid in SAMPLE_IDS:
        src = db.query(WebSource).filter(WebSource.id == sid, WebSource.is_deleted == False).first()
        if not src:
            print(f"[skip] source {sid} not found")
            continue
        # 抽样: 限制页数以提速, 不入主库配置
        src.max_pages = 5
        src.max_depth = 1
        print(f"\n=== [{src.id}] {src.name} | mode={src.scrape_mode} | url={src.url} ===")
        try:
            r = wc._run_source_crawl(db, src, task_id=f"sample-s{src.id}")
            print(f"  stats: total={r.get('total')} accepted={r.get('accepted')} rejected={r.get('rejected')}")
            if r.get("rejected_reasons"):
                for reason in r["rejected_reasons"][:5]:
                    print(f"  reject: {reason}")
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR: {e}")
finally:
    db.close()

# 抽样展示刚入库的线索
print("\n================ 抽样 web_clue (按 source_id) ================")
db = SessionLocal()
try:
    for sid in SAMPLE_IDS:
        rows = (
            db.query(WebClue)
            .filter(WebClue.source_id == sid, WebClue.is_deleted == False)
            .order_by(WebClue.id.desc())
            .limit(3)
            .all()
        )
        print(f"\n-- source_id={sid} 最近 {len(rows)} 条 --")
        for c in rows:
            print(f"  · {c.title[:60]!r}")
            print(f"    url={c.url[:90]}")
            print(f"    hit_kw={c.hit_keywords} region={c.region} category={c.category} pub={c.published_at} len={len(c.content or '')}")
finally:
    db.close()
