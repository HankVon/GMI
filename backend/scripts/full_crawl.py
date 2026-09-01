"""全量抓取(后台): 遍历全部启用源, 限制每源页数以防过久, 实时写进度日志,
跑完对本次新入库的 web_clue 做噪声比分类(低价值页 vs 真实公告).
在后端容器内运行: docker exec -d ssm-backend python full_crawl.py
"""
import os, json, time
from datetime import datetime
from app.database import SessionLocal
from app.models.web_source import WebSource
from app.models.web_clue import WebClue
from app.api.v1 import web_clues as wc
from app.services.intent_crawler import crawl_intent_source

CAP_PAGES = 10  # 限制每源页数(足够评估噪声比, 同时控制总时长)
PROGRESS = "/app/full_crawl_progress.log"
RESULT = "/app/full_crawl_result.json"

NOISE_KW = ["登录", "注册", "手机版", "手机移动版", "APP", "邮箱", "维护", "首页", "网站地图",
            "SiteMap", "导航", "版权", "帮助中心", "关于我们", "扫码", "下载客户端", "找回密码",
            "用户注册", "用户登录", "无障碍", "English"]
REAL_KW = ["公告", "公示", "中标", "招标", "出让", "结果", "意向", "采购", "交易", "成交",
           "候选", "变更", "补遗", "废标", "终止", "合同", "矿业权", "采矿权", "探矿权",
           "资源", "工程", "项目", "地块", "土地"]


def classify(title: str) -> str:
    t = title or ""
    if any(k in t for k in NOISE_KW):
        return "noise"
    if any(k in t for k in REAL_KW):
        return "real"
    return "other"


def main():
    start_dt = datetime.now()
    db = SessionLocal()
    sources = (
        db.query(WebSource)
        .filter(WebSource.is_deleted == False, WebSource.enabled == True)
        .order_by(WebSource.id)
        .all()
    )
    db.close()

    agg = {"sources": 0, "total": 0, "accepted": 0, "rejected": 0, "errors": 0}
    per_source = []
    t0 = time.time()
    with open(PROGRESS, "w", encoding="utf-8") as log:
        log.write(f"全量抓取启动: {len(sources)} 个启用源, 每源上限 {CAP_PAGES} 页\n")
        log.flush()
        for src in sources:
            sdb = SessionLocal()
            try:
                src.max_pages = min(src.max_pages or 30, CAP_PAGES)
                src.max_depth = 1
                if src.scrape_mode == "intent":
                    r = crawl_intent_source(sdb, src)
                    stored = r.get("stored", 0)
                    line = f"[{src.id}] {src.name} | intent | listed={r.get('listed')} stored={stored}"
                    agg["accepted"] += stored
                else:
                    r = wc._run_source_crawl(sdb, src, task_id=f"full-s{src.id}")
                    line = (f"[{src.id}] {src.name} | {src.scrape_mode} | "
                            f"total={r.get('total')} accepted={r.get('accepted')} rejected={r.get('rejected')}")
                    agg["total"] += r.get("total", 0)
                    agg["accepted"] += r.get("accepted", 0)
                    agg["rejected"] += r.get("rejected", 0)
                agg["sources"] += 1
            except Exception as e:  # noqa: BLE001
                line = f"[{src.id}] {src.name} | ERROR: {e}"
                agg["errors"] += 1
            finally:
                sdb.close()
            log.write(line + "\n")
            log.flush()
            per_source.append(line)

        # 噪声比: 本次新入库 web_clue 按标题分类
        cdb = SessionLocal()
        clues = (
            cdb.query(WebClue)
            .filter(WebClue.is_deleted == False, WebClue.created_at >= start_dt)
            .all()
        )
        cdb.close()
        nc = {"noise": 0, "real": 0, "other": 0, "total": len(clues)}
        samples = {"noise": [], "other": []}
        for c in clues:
            k = classify(c.title)
            nc[k] += 1
            if k == "noise" and len(samples["noise"]) < 8:
                samples["noise"].append(c.title)
            elif k == "other" and len(samples["other"]) < 8:
                samples["other"].append(c.title)

    elapsed = time.time() - t0
    summary = {
        "aggregate": agg,
        "elapsed_sec": round(elapsed, 1),
        "web_clue_new": nc,
        "noise_samples": samples,
        "per_source": per_source,
    }
    with open(RESULT, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(PROGRESS, "a", encoding="utf-8") as log:
        log.write(f"\n=== 完成: 用时 {elapsed:.1f}s ===\n")
        log.write(json.dumps({"aggregate": agg, "web_clue_new": nc}, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
