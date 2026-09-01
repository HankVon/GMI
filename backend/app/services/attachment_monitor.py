"""标讯附件抓取缺口监控。

采集 / 解析标讯时若未能拿到附件(详情页未抓到, 或附件区 <ul class='fjxx'>
无 <a href>), 在此记录一条结构化事件(JSON lines), 并按来源(source)聚合,
便于发现「哪些来源网站需要适配解析器」。

设计原则:
- 不依赖数据库变更, 纯文件日志 + 内存聚合, 接入成本低;
- 日志写入失败绝不拖垮采集主流程;
- reason 区分强弱信号:
    no_detail   详情页未抓到(空响应) —— 多为网络/反爬, 弱信号
    empty_fjxx  抓到详情但附件区无链接 —— 多为解析器需适配, 强信号
"""
import json
import os
import datetime
import logging
from collections import defaultdict

logger = logging.getLogger("attachment_monitor")

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_PATH = os.path.join(_BACKEND_ROOT, "logs", "attachment_gaps.log")


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def build_gap_marker(source: str, url: str, reason: str, title: str = "") -> dict:
    """返回应写入 bid/clue meta 的缺口标记 dict。"""
    return {
        "missing": True,
        "source": source or "",
        "url": url or "",
        "reason": reason,
        "title": title or "",
        "at": _now(),
    }


def log_gap(source: str, url: str, reason: str, title: str = "") -> dict:
    """写一条缺口事件到日志文件, 并返回 meta 标记 dict(供调用方写入 meta)。"""
    marker = build_gap_marker(source, url, reason, title)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(marker, ensure_ascii=False) + "\n")
    except Exception as exc:  # 日志失败不能拖垮采集
        logger.warning("附件缺口日志写入失败: %s", exc)
    return marker


def get_gap_stats() -> dict:
    """读取日志, 按来源聚合缺口统计。

    返回:
      {
        "total_events": int,        # 日志总条数(含重复采集)
        "distinct_urls": int,       # 去重后 url 数
        "by_source": [              # 按来源聚合(按缺口数降序)
          {"source", "empty_fjxx", "no_detail", "total", "urls":[样例..]}, ...
        ],
        "generated_at": str,
      }
    """
    events: list[dict] = []
    if os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except Exception as exc:
            logger.warning("附件缺口日志读取失败: %s", exc)

    by_source: dict[str, dict] = defaultdict(
        lambda: {"empty_fjxx": 0, "no_detail": 0, "url_set": set(), "urls": []}
    )
    seen_urls: set[str] = set()
    for ev in events:
        src = ev.get("source") or "未知来源"
        reason = ev.get("reason") or "unknown"
        agg = by_source[src]
        if reason in ("empty_fjxx", "no_detail"):
            agg[reason] += 1
        else:
            agg[reason] = agg.get(reason, 0) + 1
        u = ev.get("url")
        if u:
            agg["url_set"].add(u)
            seen_urls.add(u)
            if u not in agg["urls"] and len(agg["urls"]) < 10:
                agg["urls"].append(u)

    rows = []
    for src, agg in by_source.items():
        # total 按事件数统计(反映采集频次); distinct_urls 按去重 url(反映需适配的来源规模)
        total = sum(v for k, v in agg.items() if k not in ("urls", "url_set"))
        rows.append({
            "source": src,
            "empty_fjxx": agg.get("empty_fjxx", 0),
            "no_detail": agg.get("no_detail", 0),
            "total": total,
            "distinct_urls": len(agg["url_set"]),
            "urls": agg["urls"],
        })
    rows.sort(key=lambda r: r["total"], reverse=True)

    return {
        "total_events": len(events),
        "distinct_urls": len(seen_urls),
        "by_source": rows,
        "generated_at": _now(),
    }
