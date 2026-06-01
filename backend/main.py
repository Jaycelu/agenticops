from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from config.settings import settings
from config.logging import setup_logging
from api import (
    assets_router,
    logs_router,
    compat_router,
    settings_router,
    sites_router,
    cases_router,
    agents_router,
    memories_router,
    fabric_router,
    zabbix_router,
)
from api.ssh_management import router as ssh_management_router
from api.events import router as events_router
from api.tickets import router as tickets_router
from database import SessionLocal
from utils.cache import netbox_cache
import asyncio

logger = setup_logging()


async def cleanup_cache_task():
    """定期清理过期缓存的定时任务"""
    while True:
        await asyncio.sleep(60)  # 每分钟清理一次
        netbox_cache.cleanup_expired()


async def data_retention_cleanup_task():
    """定期执行自动化数据保留清理"""
    logger.info("Data retention cleanup task started")
    while True:
        try:
            # 每12小时执行一次
            await asyncio.sleep(43200)
            from services.data_retention_service import data_retention_service
            data_retention_service.cleanup()
        except Exception as e:
            logger.error(f"Error in data retention cleanup: {e}", exc_info=True)


async def memory_embedding_backfill_task():
    """Phase 5：定期回填 MemoryEntry.embedding。仅在配置了嵌入模型时运行。"""
    from services.embedding_service import build_embedder

    if not getattr(build_embedder(), "is_enabled", False):
        logger.info("Memory embedding backfill disabled (llm_embedding_model not configured)")
        return

    logger.info("Memory embedding backfill task started")
    while True:
        try:
            # 每小时回填一批新记忆
            await asyncio.sleep(3600)
            from database import SessionLocal
            from services.embedding_service import backfill_memory_embeddings

            db = SessionLocal()
            try:
                result = await backfill_memory_embeddings(db, limit=200)
            finally:
                db.close()
            logger.info(f"Memory embedding backfill: {result}")
        except Exception as e:
            logger.error(f"Error in memory embedding backfill: {e}", exc_info=True)


def register_execution_components():
    """Register concrete executors used by the guarded execution service."""
    from services.api_executor import api_executor
    from services.execution_engine import execution_engine
    from services.notification_executor import notification_executor
    from services.script_executor import script_executor

    execution_engine.register_executor(api_executor)
    execution_engine.register_executor(notification_executor)
    execution_engine.register_executor(script_executor)
    logger.info("Execution components registered: {}", execution_engine.list_executors())


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting NetOps AI Platform...")

    # 初始化数据库
    from database import init_db
    init_db()
    logger.info("Database initialized successfully")

    register_execution_components()

    # 启动缓存清理任务
    cleanup_task = asyncio.create_task(cleanup_cache_task())

    # 启动数据保留清理任务
    retention_cleanup_task = asyncio.create_task(data_retention_cleanup_task())

    # 启动记忆 embedding 回填任务（Phase 5）
    embedding_backfill_task = asyncio.create_task(memory_embedding_backfill_task())

    # 启动日志采样服务
    from services.log_sampler import log_sampler
    await log_sampler.start()
    logger.info("Log sampler started successfully")

    yield

    # 清理任务
    cleanup_task.cancel()
    retention_cleanup_task.cancel()
    embedding_backfill_task.cancel()

    # 停止日志采样服务
    from services.log_sampler import log_sampler
    await log_sampler.stop()

    logger.info("Shutting down NetOps AI Platform...")


app = FastAPI(
    title="NetOps AI Platform",
    description="AI-driven Network Operations Platform",
    version="0.1.1",
    lifespan=lifespan
)

allowed_origins = {
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
    settings.frontend_url,
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(origin for origin in allowed_origins if origin),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assets_router)
app.include_router(logs_router)
app.include_router(compat_router)
app.include_router(settings_router)
app.include_router(sites_router)
app.include_router(ssh_management_router)
app.include_router(events_router)
app.include_router(tickets_router)
app.include_router(cases_router)
app.include_router(agents_router)
app.include_router(memories_router)
app.include_router(fabric_router)
app.include_router(zabbix_router)


@app.get("/")
async def root():
    return {"message": "NetOps AI Platform API", "version": "0.1.1"}


@app.get("/health")
async def health_check():
    checks = {
        "database": {
            "status": "unknown",
            "message": "",
        }
    }

    overall_status = "healthy"

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {
            "status": "healthy",
            "message": "postgres connection ok",
        }
    except SQLAlchemyError as exc:
        overall_status = "unhealthy"
        checks["database"] = {
            "status": "unhealthy",
            "message": str(exc.__cause__ or exc),
        }
    finally:
        db.close()

    payload = {
        "status": overall_status,
        "checks": checks,
    }
    if overall_status == "healthy":
        return payload
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
