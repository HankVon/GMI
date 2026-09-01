# -*- coding: utf-8 -*-
"""补抓标讯公告附件链接。

背景: 采集器此前只把详情页正文转成文本入库, 附件区的 <a href> 被整段丢弃,
导致大量标讯"正文里写着有附件、meta.attachments 却是空数组", 前台无法下载。

本脚本对附件为空的已发布标讯重新抓取详情页, 解析附件区并回写 meta.attachments。

用法(backend 目录下):
    set DATABASE_URL=mysql+pymysql://ssm_user:ssm_pass@127.0.0.1:3306/ssm?charset=utf8mb4
    .venv\\Scripts\\python.exe scripts\\backfill_bid_attachments.py --dry-run        # 只统计
    .venv\\Scripts\\python.exe scripts\\backfill_bid_attachments.py --limit 20        # 试跑 20 条
    .venv\\Scripts\\python.exe scripts\\backfill_bid_attachments.py                   # 全量
    .venv\\Scripts\\python.exe scripts\\backfill_bid_attachments.py --id 383 --id 405 # 指定

选项:
    --sleep SECONDS   每次请求间隔(默认 1.5s, 用于避免被源站限流)
    --host KEYWORD    只处理来源域名含该关键字的(默认 ccgp.gov.cn)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault(
    "DATABASE_URL",
    "mysql+pymysql://ssm_user:ssm_pass@127.0.0.1:3306/ssm?charset=utf8mb4",
)

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.bid_notice import BidNotice  # noqa: E402
from app.services.clue_parsers import ccgp_detail_extras  # noqa: E402


def pending_rows(db, ids: list[int] | None, host: str):
    stmt = select(BidNotice).where(
        BidNotice.is_deleted == False,  # noqa: E712
        BidNotice.status == "published",
    )
    if ids:
        stmt = stmt.where(BidNotice.id.in_(ids))
    rows = db.execute(stmt).scalars().all()
    out = []
    for n in rows:
        meta = n.meta if isinstance(n.meta, dict) else {}
        if meta.get("attachments"):
            continue  # 已有附件, 不重复抓
        if host and host not in (n.url or ""):
            continue
        out.append(n)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只统计不写库")
    ap.add_argument("--limit", type=int, default=0, help="最多处理多少条(0=不限)")
    ap.add_argument("--sleep", type=float, default=1.5, help="请求间隔秒")
    ap.add_argument("--host", default="ccgp.gov.cn", help="只处理来源域名含该关键字的")
    ap.add_argument("--id", type=int, action="append", default=[], help="指定标讯 ID(可重复)")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        targets = pending_rows(db, args.id or None, args.host)
        if args.limit:
            targets = targets[: args.limit]
        total = len(targets)
        print(f"待补抓标讯: {total} 条" + ("  (dry-run, 不写库)" if args.dry_run else ""))
        if not total:
            return 0

        ok = fail = skip = 0
        for i, notice in enumerate(targets, 1):
            tag = f"[{i}/{total}] id={notice.id}"
            try:
                extras = ccgp_detail_extras(notice.url)
                atts = extras.get("attachments") or []
            except Exception as e:  # noqa: BLE001
                print(f"{tag} 抓取异常: {e}")
                fail += 1
                continue

            if not atts:
                print(f"{tag} 无附件(源站确实没有)  {notice.title[:30]}")
                skip += 1
            else:
                names = " | ".join(f"{a['name']}{('(' + a['size'] + ')') if a.get('size') else ''}" for a in atts)
                print(f"{tag} 补到 {len(atts)} 个: {names[:110]}")
                if not args.dry_run:
                    meta = dict(notice.meta or {})
                    meta["attachments"] = atts
                    notice.meta = meta  # JSON 列整体重新赋值以触发脏标记
                    db.commit()
                ok += 1

            if i < total:
                time.sleep(args.sleep)

        print(f"\n完成: 补到附件 {ok} 条 / 源站无附件 {skip} 条 / 失败 {fail} 条")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
