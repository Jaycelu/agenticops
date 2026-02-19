from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from config.logging import setup_logging
from api import chat_router, assets_router, logs_router, models_router
from api.sessions import router as sessions_router
from api.automation import router as automation_router
from api.abnormal_types import router as abnormal_types_router
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


async def task_executor_task():
    """定期执行待处理任务的定时任务"""
    logger.info("Task executor task started")
    while True:
        try:
            await asyncio.sleep(30)  # 每30秒检查一次
            from services.automation_orchestrator import automation_orchestrator
            from services.decision_service import decision_service
            from services.confirmation_service import confirmation_service
            from services.approval_service import approval_service

            # 处理pending任务
            await automation_orchestrator.process_pending_tasks()

            # 处理等待确认的任务（自动确认低风险任务）
            waiting_tasks = await confirmation_service.get_pending_confirmations()
            for task_info in waiting_tasks:
                task_id = task_info['task_id']
                # 这里可以添加自动确认逻辑，例如：
                # - 如果任务创建时间超过一定时间且无人确认，自动拒绝
                # - 或者根据其他条件自动确认
                pass

        except Exception as e:
            logger.error(f"Error in task executor: {e}", exc_info=True)


async def abnormal_tracker_cleanup_task():
    """定期清理过期异常状态的定时任务"""
    logger.info("Abnormal tracker cleanup task started")
    while True:
        try:
            await asyncio.sleep(300)  # 每5分钟清理一次
            from services.abnormal_tracker import abnormal_tracker
            abnormal_tracker.cleanup_old_states()
        except Exception as e:
            logger.error(f"Error in abnormal tracker cleanup: {e}", exc_info=True)


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

    # 启动任务执行器
    task_executor = asyncio.create_task(task_executor_task())

    # 启动异常跟踪器清理任务
    abnormal_tracker_cleanup = asyncio.create_task(abnormal_tracker_cleanup_task())

    # 启动数据保留清理任务
    retention_cleanup_task = asyncio.create_task(data_retention_cleanup_task())

    # 启动日志采样服务
    from services.log_sampler import log_sampler
    await log_sampler.start()
    logger.info("Log sampler started successfully")

    yield

    # 清理任务
    cleanup_task.cancel()
    task_executor.cancel()
    abnormal_tracker_cleanup.cancel()
    retention_cleanup_task.cancel()

    # 停止日志采样服务
    from services.log_sampler import log_sampler
    await log_sampler.stop()

    logger.info("Shutting down NetOps AI Platform...")


app = FastAPI(
    title="NetOps AI Platform",
    description="AI-driven Network Operations Platform",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000", "http://10.128.206.214:5173", "http://10.128.206.214:5174", "http://10.128.206.214:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(assets_router)
app.include_router(sessions_router)
app.include_router(logs_router)
app.include_router(models_router)
app.include_router(automation_router)
app.include_router(abnormal_types_router)
app.include_router(ssh_management_router)
app.include_router(command_templates_router)
app.include_router(events_router)
app.include_router(tickets_router)


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
