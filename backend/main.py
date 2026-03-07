from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from config.settings import settings
from config.logging import setup_logging
from api import (
    assets_router,
    logs_router,
    models_router,
    cases_router,
    agents_router,
    memories_router,
    fabric_router,
)
from api.automation import router as automation_router
from api.ssh_management import router as ssh_management_router
from api.command_templates import router as command_templates_router
from api.events import router as events_router
from api.tickets import router as tickets_router
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting NetOps AI Platform...")

    # 初始化数据库
    from database import init_db
    init_db()
    logger.info("Database initialized successfully")

    # 启动缓存清理任务
    cleanup_task = asyncio.create_task(cleanup_cache_task())

    # 启动数据保留清理任务
    retention_cleanup_task = asyncio.create_task(data_retention_cleanup_task())

    yield

    # 清理任务
    cleanup_task.cancel()
    retention_cleanup_task.cancel()

    logger.info("Shutting down NetOps AI Platform...")


app = FastAPI(
    title="NetOps AI Platform",
    description="AI-driven Network Operations Platform",
    version="0.1.0",
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
app.include_router(models_router)
app.include_router(automation_router)
app.include_router(ssh_management_router)
app.include_router(command_templates_router)
app.include_router(events_router)
app.include_router(tickets_router)
app.include_router(cases_router)
app.include_router(agents_router)
app.include_router(memories_router)
app.include_router(fabric_router)


@app.get("/")
async def root():
    return {"message": "NetOps AI Platform API", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
