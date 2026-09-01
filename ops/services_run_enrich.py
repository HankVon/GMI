"""全量深度补全: 把剩余未标记的 CO-PIP% 单位补全(阻塞式, 供 nohup 后台运行)。"""
import os
import sys
import time
sys.path.insert(0, "/app")
from app.database import SessionLocal
from app.models.company import Company
from sqlalchemy import select
from app.services.data_pipeline import _missing_core_fields, _needs_enrich, _is_sc_company
from app.services.company_free_enrich import enrich_company_free

db = SessionLocal()
try:
    cands = db.execute(
        select(Company).where(Company.code.like("CO-PIP%"), Company.is_deleted == False)
    ).scalars().all()
    pending = [c for c in cands if _needs_enrich(c) and not (c.ext_attrs or {}).get("_enrich_tried")]
    pending.sort(key=lambda c: (0 if _is_sc_company(c) else 1,
                                0 if any(m in {"地址","甲方联系方式","联系电话","法定代表人","经营范围","登记机关"} for m in _missing_core_fields(c)) else 1,
                                -len(_missing_core_fields(c)), c.id))
    total = len(pending)
    print(f"[enrich] 待补单位 {total} 个, 开始全量补全...", flush=True)
    ok = skip = fail = 0
    t_start = time.time()
    for i, co in enumerate(pending, 1):
        try:
            r = enrich_company_free(db, co)
            if r.get("updated"):
                ok += 1
                print(f"[enrich] #{i} OK  {co.name} (+{len(r['updated'])}字段/{r.get('source')})", flush=True)
            else:
                skip += 1
                print(f"[enrich] #{i} --  {co.name}: {r.get('message','')}", flush=True)
            e = dict(co.ext_attrs or {})
            e["_enrich_tried"] = 1
            co.ext_attrs = e
            db.commit()
        except Exception as ex:
            fail += 1
            print(f"[enrich] #{i} FAIL {co.name}: {ex}", flush=True)
            db.rollback()
        if i % 5 == 0 or i == total:
            avg = (time.time() - t_start) / i
            remain = avg * (total - i)
            print(f"[enrich] 进度 {i}/{total} (ok={ok} skip={skip} fail={fail}) 单均{avg:.0f}s 剩余~{remain/60:.0f}min", flush=True)
    print(f"[enrich] 完成: 共 {total}, 补到 {ok}, 无新字段 {skip}, 失败 {fail}", flush=True)
finally:
    db.close()
