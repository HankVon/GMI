"""数据流水线实时过程日志(内存环形缓冲, 供前端「一键执行」实时查看进度)。

从 data_pipeline.py 拆出: 完全自包含, 不依赖流水线其他逻辑。
"""
import logging
import threading
from datetime import datetime

logger = logging.getLogger("data_pipeline")

_pipeline_logs: list = []
_pipeline_log_lock = threading.Lock()
_PIPELINE_LOG_MAX = 1500

_STAGE_ZH = {"collect": "采集", "filter": "筛选入库", "graph": "图谱构建", "backfill": "前端回填"}


def push_log(stage: str, msg: str, level: str = "info") -> None:
    """追加流水线过程日志。stage ∈ collect/filter/graph/backfill/general。"""
    entry = {
        "ts": datetime.now().strftime("%H:%M:%S"),
        "stage": stage,
        "msg": str(msg),
        "level": level,
    }
    with _pipeline_log_lock:
        _pipeline_logs.append(entry)
        if len(_pipeline_logs) > _PIPELINE_LOG_MAX:
            del _pipeline_logs[: len(_pipeline_logs) - _PIPELINE_LOG_MAX]


def get_pipeline_logs(limit: int = 200) -> list:
    with _pipeline_log_lock:
        return list(_pipeline_logs[-limit:])


def clear_pipeline_logs() -> None:
    with _pipeline_log_lock:
        _pipeline_logs.clear()
