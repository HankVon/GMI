"""轻量进程内请求限速 — 登录接口防暴力破解。

单实例部署场景下足够; 多实例部署时应替换为 Redis 分布式计数。
登录失败 N 次/窗口内锁定该 IP(HTTP 429), 成功登录即清零。
阈值参数来自 Settings(LOGIN_MAX_FAILURES / LOGIN_WINDOW_SECONDS)。
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, status

from app.config import settings

_MAX_FAILURES = settings.LOGIN_MAX_FAILURES
_WINDOW_SECONDS = settings.LOGIN_WINDOW_SECONDS

_failures: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def check_login_rate_limit(ip: str) -> None:
    """登录前调用: 若该 IP 在窗口内失败已达上限, 抛 429 拒绝。"""
    if not ip:
        return
    with _lock:
        now = time.time()
        dq = _failures.get(ip)
        if not dq:
            return
        while dq and now - dq[0] > _WINDOW_SECONDS:
            dq.popleft()
        if len(dq) >= _MAX_FAILURES:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"登录尝试次数过多, 请 {_WINDOW_SECONDS // 60} 分钟后再试",
            )


def record_login_failure(ip: str) -> None:
    """登录失败时调用: 记录失败时间点(滑动窗口)。"""
    if not ip:
        return
    with _lock:
        _failures[ip].append(time.time())


def record_login_success(ip: str) -> None:
    """登录成功时调用: 清零该 IP 的失败计数。"""
    if not ip:
        return
    with _lock:
        _failures.pop(ip, None)
