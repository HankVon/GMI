"""SSM 项目基石数据平台 — FastAPI 主入口"""
import logging
import os
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.ai import router as ai_router
from app.api.v1.audit import router as audit_router
from app.api.v1.bids import router as bids_router, tender_router
from app.api.v1.bid_admin import router as bid_admin_router
from app.api.v1.bid_tags import router as bid_tags_router
from app.api.v1.bid_attachments import router as bid_attachments_router
from app.api.v1.business_network import router as business_network_router
from app.api.v1.companies import router as companies_router
from app.api.v1.company_detail import router as company_detail_router
from app.api.v1.favorites import router as favorites_router
from app.api.v1.combined_query import router as combined_query_router
from app.api.v1.content import router as content_router
from app.api.v1.cms import router as cms_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.dynamic_crud import router as dynamic_crud_router
from app.api.v1.excel import router as excel_router
from app.api.v1.field_meta import router as field_meta_router
from app.api.v1.geo import router as geo_router
from app.api.v1.intelligence import router as intelligence_router
from app.api.v1.intent import router as intent_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.marketing import router as marketing_router
from app.api.v1.network import router as network_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.opportunities import router as opportunities_router
from app.api.v1.intelligence_admin import router as intelligence_admin_router
from app.api.v1.owners import router as owners_router
from app.api.v1.reports import router as reports_router
from app.api.v1.public import router as public_router
from app.api.v1.option_sets import router as option_sets_router
from app.api.v1.persons import router as persons_router
from app.api.v1.pipeline import router as pipeline_router
from app.api.v1.project_companies import router as project_companies_router
from app.api.v1.project_context import router as project_context_router
from app.api.v1.project_members import router as project_members_router
from app.api.v1.project_progress import router as project_progress_router
from app.api.v1.project_tracker import router as project_tracker_router
from app.api.v1.projects import router as projects_router
from app.api.v1.rbac import router as rbac_router
from app.api.v1.rbac_admin import router as rbac_admin_router
from app.api.v1.search import router as search_router
from app.api.v1.tenders_search import router as tenders_search_router
from app.api.v1.web_clues import router as web_clues_router
from app.config import settings
from app.database import SessionLocal
from app.middleware.audit import AuditMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.services.cache_service import cache_service
from app.services.migrate import run_migrations

startup_logger = logging.getLogger("startup")
_MIGRATION_STATUS: dict | None = None


def _setup_logging() -> None:
    """日志持久化: 输出到文件(轮转 10MB×5) + 控制台。目录不存在时静默降级为仅控制台。"""
    try:
        log_dir = os.getenv("LOG_DIR", "/app/logs")
        os.makedirs(log_dir, exist_ok=True)
        handler = RotatingFileHandler(
            os.path.join(log_dir, "app.log"),
            maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        ))
        root = logging.getLogger()
        root.addHandler(handler)
        if root.level == logging.WARNING:
            root.setLevel(logging.INFO)
        startup_logger.info("[logging] 日志文件已启用: %s", os.path.join(log_dir, "app.log"))
    except Exception as e:  # noqa: BLE001 - 日志初始化失败不影响服务
        startup_logger.warning("[logging] 日志文件初始化失败(仅控制台): %s", e)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _MIGRATION_STATUS
    _setup_logging()
    # 启动迁移(幂等补列)。失败不阻断启动, 但必须 ERROR 告警以便运维感知
    try:
        db = SessionLocal()
        try:
            _MIGRATION_STATUS = run_migrations(db)
            # 清理过期的对象级授权(启动时幂等)
            try:
                from app.services.data_scope_service import clean_expired_grants
                n = clean_expired_grants(db)
                if n:
                    startup_logger.info("清理过期数据授权 %d 条", n)
            except Exception:  # noqa: BLE001
                startup_logger.warning("清理过期数据授权失败(不影响启动)")
            # 营销智能体基础数据种子(渠道/默认引擎/默认关键词, 幂等)
            from app.services.marketing import seed_marketing_basics
            seed_marketing_basics(db)
        finally:
            db.close()
    except Exception:  # 迁移失败不阻断启动, 但需告警(异常详情由 exc_info 堆栈输出)
        startup_logger.exception("启动数据库迁移失败(功能可能不完整)")
    await cache_service.connect()
    # 启动定时任务(意向源抓取/人脉库重建)
    try:
        from app.services.scheduler import start_scheduler
        start_scheduler()
    except Exception:  # 调度器失败不阻断启动, 但需告警(异常详情由 exc_info 堆栈输出)
        startup_logger.exception("启动定时任务失败(意向/人脉周期任务不可用)")
    yield
    try:
        from app.services.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:  # noqa: BLE001, S110 - 关停异常不影响退出
        pass
    await cache_service.close()


app = FastAPI(
    title=settings.APP_NAME, version=settings.APP_VERSION,
    lifespan=lifespan, docs_url="/docs", redoc_url="/redoc",
)

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins_list,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(AuditMiddleware)
app.add_middleware(RateLimitMiddleware)
# 压缩 API JSON 响应: 域名走 Cloudflare 免费隧道带宽窄, gzip 可省 70-80% 传输体积
app.add_middleware(GZipMiddleware, minimum_size=500)


@app.middleware("http")
async def _upload_size_limit(request: Request, call_next):
    """文件上传大小限制: multipart 请求按 Content-Length 拒绝超限(防大文件拖垮服务)。"""
    if (request.method in ("POST", "PUT", "PATCH")
            and "multipart/form-data" in request.headers.get("content-type", "")
            and request.headers.get("content-length")):
        try:
            size = int(request.headers.get("content-length") or 0)
        except ValueError:
            size = 0
        if size > settings.MAX_UPLOAD_MB * 1024 * 1024:
            return JSONResponse(status_code=413, content={
                "success": False, "detail": f"上传文件过大, 上限 {settings.MAX_UPLOAD_MB} MB",
            })
    return await call_next(request)

app.include_router(rbac_router, prefix="/api/v1")
app.include_router(rbac_admin_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(persons_router, prefix="/api/v1")
app.include_router(project_members_router, prefix="/api/v1")
app.include_router(field_meta_router, prefix="/api/v1")
app.include_router(option_sets_router, prefix="/api/v1")
app.include_router(excel_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(dynamic_crud_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(tenders_search_router, prefix="/api/v1")
app.include_router(companies_router, prefix="/api/v1")
app.include_router(company_detail_router, prefix="/api/v1")
app.include_router(favorites_router, prefix="/api/v1")
app.include_router(combined_query_router, prefix="/api/v1")
app.include_router(project_companies_router, prefix="/api/v1")
app.include_router(project_progress_router, prefix="/api/v1")
app.include_router(network_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(bids_router, prefix="/api/v1")
app.include_router(tender_router, prefix="/api/v1")
app.include_router(bid_admin_router, prefix="/api/v1")
app.include_router(bid_tags_router, prefix="/api/v1")
app.include_router(bid_attachments_router, prefix="/api/v1")
app.include_router(web_clues_router, prefix="/api/v1")
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(business_network_router, prefix="/api/v1")
app.include_router(intent_router, prefix="/api/v1")
app.include_router(intelligence_router, prefix="/api/v1")
app.include_router(project_context_router, prefix="/api/v1")
app.include_router(project_tracker_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(geo_router, prefix="/api/v1")
app.include_router(content_router, prefix="/api/v1")
app.include_router(marketing_router, prefix="/api/v1")
app.include_router(cms_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(opportunities_router, prefix="/api/v1")
app.include_router(intelligence_admin_router, prefix="/api/v1")
app.include_router(owners_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
# 对外官网公开接口(无需登录, 仅脱敏聚合数据)
app.include_router(public_router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health_check():
    """健康检查: 探测 MySQL/Redis/Neo4j 依赖状态, 供运维与探活使用。"""
    from sqlalchemy import text
    deps: dict[str, str] = {}
    # MySQL
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        deps["mysql"] = "ok"
    except Exception:  # noqa: BLE001
        deps["mysql"] = "down"
    # Redis
    deps["redis"] = "ok" if await cache_service.ping() else "down"
    # Neo4j(熔断窗口内直接判 down, 快速返回)
    try:
        from app.services.neo4j_sync import _get_driver
        driver = _get_driver()
        if driver is not None:
            driver.verify_connectivity()
            deps["neo4j"] = "ok"
        else:
            deps["neo4j"] = "down"
    except Exception:  # noqa: BLE001
        deps["neo4j"] = "down"
    overall = "ok" if set(deps.values()) == {"ok"} else "degraded"
    return {"status": overall, "version": settings.APP_VERSION, "dependencies": deps, "migrations": _MIGRATION_STATUS}


# ── 全局异常处理: 统一 JSON 响应格式, 生产环境不泄露内部堆栈 ──
@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(request: Request, exc: StarletteHTTPException):
    """统一 HTTP 异常响应为 {success, detail}, 兼容前端 detail 字符串判断。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError):
    """参数校验失败(422): detail 用可读字符串, 明细放入 errors(前端已按字符串处理)。"""
    msgs = []
    for e in exc.errors():
        loc = ".".join(str(p) for p in e.get("loc", [])[1:])
        msgs.append(f"{loc}: {e.get('msg', '参数错误')}")
    return JSONResponse(
        status_code=422,
        content={"success": False, "detail": "参数校验失败", "errors": msgs[:5]},
    )


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """未捕获异常: 记录完整堆栈到日志, 生产环境仅返回通用提示。"""
    logging.getLogger("app.error").exception(
        "未捕获异常: %s %s", request.method, request.url.path
    )
    detail = f"{type(exc).__name__}: {exc}" if settings.DEBUG else "服务器内部错误"
    return JSONResponse(status_code=500, content={"success": False, "detail": detail})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=settings.DEBUG)
