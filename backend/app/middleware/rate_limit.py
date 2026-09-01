"""API 通用限流中间件 — Redis 分布式滑动窗口计数。

设计:
  - 按客户端 IP 计数(单位机局域网共用出口, 阈值可配)。
  - Redis 不可用/熔断时降级放行(不阻断业务, 与缓存策略一致)。
  - 登录接口有专门的防暴力破解, 健康检查/文档接口不参与限流。
"""
from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.services.cache_service import cache_service

logger = logging.getLogger("ratelimit")

_SKIP_PATHS = {"/api/v1/health", "/api/v1/auth/login"}
_SKIP_PREFIXES = ("/docs", "/redoc", "/openapi.json")


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (path in _SKIP_PATHS or path.startswith(_SKIP_PREFIXES)
                or not path.startswith("/api/v1")):
            return await call_next(request)

        client_ip = request.client.host if request.client else "0.0.0.0"
        key = f"rl:1m:{client_ip}"

        n = await cache_service.incr(key, ttl=settings.RATE_LIMIT_WINDOW)
        if n is not None and n > settings.RATE_LIMIT_PER_MINUTE:
            logger.warning("[ratelimit] ip=%s exceeded path=%s count=%s", client_ip, path, n)
            return JSONResponse(status_code=429, content={
                "success": False,
                "detail": "请求过于频繁, 请稍后再试",
            })
        return await call_next(request)
