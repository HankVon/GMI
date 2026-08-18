"""审计中间件 — 记录API操作日志（异步 + 健壮性增强）"""
import time
import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.background import BackgroundTask, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.audit_service import log_action
from app.services.auth_service import decode_access_token

logger = logging.getLogger("audit")


class AuditMiddleware(BaseHTTPMiddleware):
    """全局审计中间件: 拦截写操作(POST/PUT/PATCH/DELETE)并记录。审计写库失败不影响业务。"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # ★ 注意: 不在中间件中读取 request.body()。
        # BaseHTTPMiddleware 中读取 body 是反模式: body 流只能消费一次,
        # 预读会干扰路由的请求体解析(导致 400), call_next 后读取会永久挂起(响应无法返回)。
        # 审计不记录请求体内容(登录等请求含密码等敏感信息, 更不应入库)。

        response: Response = await call_next(request)

        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            user_info = self._extract_user(request)
            resource_type, resource_id = self._parse_resource(request.url.path)
            detail = {
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params),
                "status_code": response.status_code if hasattr(response, 'status_code') else 0,
                "duration_ms": round(time.time() - start_time, 2),
            }
            # 异步写审计（BackgroundTask 在响应发送后执行）
            task = BackgroundTask(
                _write_audit_log_async,
                user_id=user_info["user_id"],
                username=user_info["username"],
                action=request.method.lower(),
                resource_type=resource_type,
                resource_id=resource_id,
                detail=detail,
                ip=request.client.host if request.client else None,
                ua=request.headers.get("User-Agent"),
            )
            # 合并而非覆盖 response.background: 路由可能已挂业务后台任务,
            # 直接覆盖会导致业务任务丢失。按 starlette 三种形态分别合并。
            if isinstance(response.background, BackgroundTasks):
                response.background.add_task(task.func, *task.args, **task.kwargs)
            elif response.background is None:
                response.background = task
            else:
                # 已是单个 BackgroundTask(或 callable): 包装进 BackgroundTasks 保序执行
                existing = response.background
                tasks = BackgroundTasks()
                if isinstance(existing, BackgroundTask):
                    tasks.add_task(existing.func, *existing.args, **existing.kwargs)
                tasks.add_task(task.func, *task.args, **task.kwargs)
                response.background = tasks

        return response

    def _extract_user(self, request: Request) -> dict:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            payload = decode_access_token(auth_header[7:])
            if payload:
                return {
                    "user_id": int(payload.get("sub", 0)) or None,
                    "username": payload.get("username", ""),
                }
        return {"user_id": None, "username": None}

    def _parse_resource(self, path: str) -> tuple:
        parts = path.split("/")
        resource_type = "unknown"
        resource_id = None
        if len(parts) >= 4 and parts[1] == "api" and parts[2] == "v1":
            resource_type = parts[3] if len(parts) > 3 else "unknown"
            if len(parts) > 4 and parts[4].isdigit():
                resource_id = int(parts[4])
        return resource_type, resource_id


async def _write_audit_log_async(
    user_id, username, action, resource_type, resource_id, detail, ip, ua
):
    """后台任务：异步写审计日志，失败仅记日志不影响主请求"""
    db: Session | None = None
    try:
        db = SessionLocal()
        log_action(
            db=db,
            user_id=user_id,
            username=username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail,
            ip_address=ip,
            user_agent=ua,
        )
        db.commit()
    except Exception as e:
        logger.exception("[audit] async write failed: %s", e)
        if db:
            try:
                db.rollback()
            except Exception:
                pass
    finally:
        if db:
            try:
                db.close()
            except Exception:
                pass
