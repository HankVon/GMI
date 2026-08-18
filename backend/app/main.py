"""SSM 项目基石数据平台 — FastAPI 主入口"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.ai import router as ai_router
from app.api.v1.audit import router as audit_router
from app.api.v1.bids import router as bids_router
from app.api.v1.business_network import router as business_network_router
from app.api.v1.companies import router as companies_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.dynamic_crud import router as dynamic_crud_router
from app.api.v1.excel import router as excel_router
from app.api.v1.field_meta import router as field_meta_router
from app.api.v1.intelligence import router as intelligence_router
from app.api.v1.intent import router as intent_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.network import router as network_router
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
from app.api.v1.web_clues import router as web_clues_router
from app.config import settings
from app.database import SessionLocal
from app.middleware.audit import AuditMiddleware
from app.services.cache_service import cache_service
from app.services.migrate import run_migrations

startup_logger = logging.getLogger("startup")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 启动迁移(幂等补列)。失败不阻断启动, 但必须 ERROR 告警以便运维感知
    try:
        db = SessionLocal()
        try:
            run_migrations(db)
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
app.include_router(companies_router, prefix="/api/v1")
app.include_router(project_companies_router, prefix="/api/v1")
app.include_router(project_progress_router, prefix="/api/v1")
app.include_router(network_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(bids_router, prefix="/api/v1")
app.include_router(web_clues_router, prefix="/api/v1")
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(business_network_router, prefix="/api/v1")
app.include_router(intent_router, prefix="/api/v1")
app.include_router(intelligence_router, prefix="/api/v1")
app.include_router(project_context_router, prefix="/api/v1")
app.include_router(project_tracker_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=settings.DEBUG)
