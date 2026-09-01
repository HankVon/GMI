"""Excel 导入后台任务 — 大文件导入后台执行, 前端轮询进度, 避免请求内同步等待超时。

用法:
  tid = submit_import("projects", file_bytes, user_id, runner)
  其中 runner(db_session, file_bytes, progress) -> dict
  progress(stage="", imported=0, updated=0, skipped=0, failed=0, log="") 供实时进度推送

任务结果在内存保留 10 分钟(前端轮询拉取), 之后清理防内存泄漏。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Callable, Optional

_TASKS: dict[str, dict] = {}
_LOCK = threading.Lock()
_TTL_SECONDS = 600  # 任务结果保留 10 分钟
_MAX_LOGS = 300


def _cleanup() -> None:
    """清理已结束且超过 TTL 的任务。"""
    now = time.time()
    for tid in list(_TASKS):
        t = _TASKS.get(tid)
        if t and t["status"] != "running" and t.get("finished_at") and now - t["finished_at"] > _TTL_SECONDS:
            _TASKS.pop(tid, None)


def submit_import(entity_type: str, file_bytes: bytes, user_id: int,
                  runner: Callable[[object, bytes, Callable], dict]) -> str:
    """提交导入任务并立即返回 task_id, 后台线程执行。

    runner(db_session, file_bytes, progress) -> result dict
    """
    tid = uuid.uuid4().hex[:12]
    task = {
        "id": tid,
        "entity_type": entity_type,
        "user_id": user_id,
        "status": "running",
        "stage": "正在解析文件…",
        "imported": 0, "updated": 0, "skipped": 0, "failed": 0,
        "logs": [],
        "result": None,
        "error": None,
        "started_at": time.time(),
        "finished_at": None,
    }
    with _LOCK:
        _cleanup()
        _TASKS[tid] = task

    def _progress(stage: str = "", imported: int = 0, updated: int = 0,
                  skipped: int = 0, failed: int = 0, log: Optional[str] = None) -> None:
        with _LOCK:
            t = _TASKS.get(tid)
            if not t:
                return
            if stage:
                t["stage"] = stage
            t["imported"] = imported
            t["updated"] = updated
            t["skipped"] = skipped
            t["failed"] = failed
            if log:
                t["logs"].append(log)
                if len(t["logs"]) > _MAX_LOGS:
                    t["logs"] = t["logs"][-_MAX_LOGS:]

    def _worker() -> None:
        from app.database import SessionLocal
        sdb = SessionLocal()
        try:
            result = runner(sdb, file_bytes, _progress) or {}
            with _LOCK:
                t = _TASKS.get(tid)
                if t:
                    t["status"] = "done"
                    t["result"] = result
                    t["stage"] = "导入完成"
                    t["finished_at"] = time.time()
                    # 补充最终计数
                    for k in ("imported", "updated", "skipped", "failed"):
                        if result.get(k) is not None:
                            t[k] = result[k]
                    for lg in (result.get("log") or [])[len(t["logs"]):]:
                        t["logs"].append(lg)
                        if len(t["logs"]) > _MAX_LOGS:
                            t["logs"] = t["logs"][-_MAX_LOGS:]
        except Exception as e:  # noqa: BLE001
            with _LOCK:
                t = _TASKS.get(tid)
                if t:
                    t["status"] = "failed"
                    t["error"] = str(e)
                    t["stage"] = "导入失败"
                    t["finished_at"] = time.time()
        finally:
            sdb.close()

    threading.Thread(target=_worker, daemon=True).start()
    return tid


def get_import_task(task_id: str) -> Optional[dict]:
    """查询任务状态(返回副本, 避免外部修改内部状态)。"""
    with _LOCK:
        t = _TASKS.get(task_id)
        return dict(t) if t else None
