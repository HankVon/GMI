# -*- coding: utf-8 -*-
"""真实环境验证 TenderDetailService.build() 完整链路。

用法(在 backend 目录下):
    set DATABASE_URL=mysql+pymysql://ssm_user:ssm_pass@127.0.0.1:3306/ssm?charset=utf8mb4
    .venv\\Scripts\\python.exe scripts\\verify_tender_detail.py [bid_id ...]

输出每个标讯的关键字段修复前后对比, 断言不通过会抛出 AssertionError。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault(
    "DATABASE_URL",
    "mysql+pymysql://ssm_user:ssm_pass@127.0.0.1:3306/ssm?charset=utf8mb4",
)

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.bid_notice import BidNotice  # noqa: E402
from app.services.tender_detail_service import TenderDetailService  # noqa: E402


def kv_of(data, label: str):
    for row in data.kv:
        if row.label == label:
            return row.field.displayText
    return None


def time_of(data, label: str):
    for row in data.timeMatrix:
        if row.label == label:
            return row.field.displayText
    return None


def check(bid_id: int, db) -> dict:
    notice = db.execute(
        select(BidNotice).where(BidNotice.id == bid_id, BidNotice.is_deleted == False)  # noqa: E712
    ).scalars().first()
    if not notice:
        raise AssertionError(f"标讯 {bid_id} 不存在")

    data = TenderDetailService(db, {"user_id": 0}).build(notice)

    print(f"\n{'=' * 72}\n标讯 {bid_id}  {notice.title[:40]}")
    print(f"  类型={notice.notice_type}  地区={notice.region}  正文={len(data.body)} 字")

    print("  -- 基本信息(补抽回填后) --")
    for label in ("招标代理", "建设规模", "建设工期", "预算金额"):
        print(f"     {label}: {kv_of(data, label)}")

    print("  -- 关键时间 --")
    for label in ("报名截止", "文件获取截止", "投标截止", "开标时间"):
        print(f"     {label}: {time_of(data, label)}")

    print("  -- 项目编号 --", data.header.projectCode)
    print("  -- 中标供应商 --", len(data.suppliers), "家")
    for s in data.suppliers:
        print(f"     {s.rank}. {s.name}  ¥{s.amount_text}  得分={s.score}")
        print(f"        地址={s.address}")
    print("  -- 附件 --", len(data.attachments), "个")
    for a in data.attachments:
        name = a.get("name") if isinstance(a, dict) else str(a)
        url = (a.get("url") if isinstance(a, dict) else None) or "(无链接, 仅正文线索)"
        print(f"     {name}  ->  {str(url)[:70]}")
    print("  -- 时间线 --", [(e.name, e.date) for e in data.timeline] or "空")
    print("  -- 标签 --", [t.label for t in data.tags])
    e = data.enriched
    print("  -- 补抽 --", {k: v for k, v in e.items() if v not in (None, [], "")})

    # ---- 断言: 契约完整性 ----
    assert hasattr(data, "suppliers"), "schema 缺少 suppliers"
    assert hasattr(data, "enriched"), "schema 缺少 enriched"
    for row in data.kv:
        assert row.field.displayText, f"kv {row.label} 缺少 displayText"
    assert "\nvar myDate" not in data.body, "正文仍含 JS 噪声"
    assert "主办单位：" not in data.body, "正文仍含备案噪声"
    return {"id": bid_id, "suppliers": len(data.suppliers), "attachments": len(data.attachments)}


def main():
    ids = [int(x) for x in sys.argv[1:]] or [383, 405]
    db = SessionLocal()
    summary = []
    try:
        for bid_id in ids:
            summary.append(check(bid_id, db))
    finally:
        db.close()
    print(f"\n{'=' * 72}\n汇总: {summary}")
    print("全部断言通过")


if __name__ == "__main__":
    main()
