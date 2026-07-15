from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from contextlib import asynccontextmanager
from sqlalchemy import func, text
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
    auth_router,
    identity_admin_router,
    probes_router,
    webhooks_router,
    ingestion_router,
    events_router,
)
from api.ssh_management import router as ssh_management_router
from api.tickets import router as tickets_router
from database import SessionLocal
from auth.csrf import CSRFMiddleware
from auth.dependencies import require_permissions
from auth.rbac import Permission
from observability.middleware import ObservabilityMiddleware
from observability.metrics import metrics_registry
from api.errors import install_error_handlers

logger = setup_logging()


def register_execution_components():
    """Register concrete executors used by the guarded execution service."""
    from services.api_executor import api_executor
    from services.execution_engine import execution_engine
    from services.notification_executor import notification_executor
    from services.script_executor import script_executor
    from services.ssh_mutation_executor import ssh_mutation_executor

    execution_engine.register_executor(api_executor)
    execution_engine.register_executor(notification_executor)
    execution_engine.register_executor(script_executor)
    execution_engine.register_executor(ssh_mutation_executor)
    logger.info("Execution components registered: {}", execution_engine.list_executors())


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting NetOps AI Platform...")

    # 数据库迁移必须由部署步骤显式执行；应用启动只校验版本。
    from database import init_db
    init_db()
    logger.info("Database migration revision verified")

    from auth.session_service import auth_secret_bytes
    auth_secret_bytes()
    logger.info("Authentication secret policy verified")

    register_execution_components()

    yield

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

app.add_middleware(CSRFMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(origin for origin in allowed_origins if origin),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ObservabilityMiddleware)
install_error_handlers(app)

read_dependency = [Depends(require_permissions(Permission.CASES_READ.value))]
app.include_router(assets_router, dependencies=read_dependency)
app.include_router(logs_router, dependencies=read_dependency)
app.include_router(
    compat_router,
    dependencies=[Depends(require_permissions(Permission.AUTOMATION_MANAGE.value))],
)
app.include_router(
    settings_router,
    dependencies=[Depends(require_permissions(Permission.INTEGRATIONS_MANAGE.value))],
)
app.include_router(sites_router, dependencies=read_dependency)
app.include_router(
    ssh_management_router,
    dependencies=[Depends(require_permissions(Permission.CREDENTIALS_MANAGE.value))],
)
app.include_router(events_router)
app.include_router(tickets_router, dependencies=read_dependency)
app.include_router(cases_router, dependencies=read_dependency)
app.include_router(agents_router, dependencies=read_dependency)
app.include_router(memories_router, dependencies=read_dependency)
app.include_router(fabric_router, dependencies=read_dependency)
app.include_router(zabbix_router, dependencies=read_dependency)
app.include_router(auth_router)
app.include_router(identity_admin_router)
app.include_router(probes_router)
app.include_router(webhooks_router)
app.include_router(ingestion_router)


@app.get("/")
async def root():
    return {"message": "NetOps AI Platform API", "version": "0.1.1"}


@app.get("/health/live")
async def health_live():
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        from database import current_database_revisions, expected_database_revisions

        current = current_database_revisions(db.connection())
        expected = expected_database_revisions()
        if current != expected:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "checks": {"database": "schema_revision_mismatch"}},
            )
        return {"status": "ready", "checks": {"database": "ready"}}
    except SQLAlchemyError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "checks": {"database": "unavailable"}},
        )
    finally:
        db.close()


@app.get("/health")
async def health_compatibility():
    return await health_ready()


@app.get("/health/dependencies")
async def health_dependencies():
    from services.integration_config_service import integration_config_service

    db = SessionLocal()
    try:
        from models.auth import IdentityProvider
        from models.ingestion import IngestionCheckpoint
        from models.runtime import WorkerHeartbeat
        from datetime import datetime, timedelta, timezone

        netbox = integration_config_service.get_netbox_runtime_config(db=db)
        elk = integration_config_service.get_elk_runtime_config(db=db)
        zabbix = integration_config_service.get_zabbix_runtime_config(db=db)
        enabled_identity_count = db.query(IdentityProvider.id).filter(IdentityProvider.enabled.is_(True)).count()
        lag = db.query(func.max(IngestionCheckpoint.lag_seconds)).scalar()
        worker_alive = db.query(WorkerHeartbeat.worker_name).filter(
            WorkerHeartbeat.last_seen_at >= datetime.now(timezone.utc) - timedelta(minutes=2),
            WorkerHeartbeat.status.in_(["healthy", "degraded"]),
        ).first()
        return {
            "status": "ok",
            "dependencies": {
                "netbox": "configured" if netbox.get("enabled") else "disabled",
                "elk": "configured" if elk.get("enabled") else "disabled",
                "zabbix": "configured" if zabbix.get("enabled") else "disabled",
                "identity": "configured" if enabled_identity_count else "missing",
                "elk_checkpoint_lag_seconds": lag,
                "worker": "alive" if worker_alive else "unavailable",
            },
        }
    finally:
        db.close()


@app.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    from models.execution_job import ExecutionJob
    from models.ingestion import IngestionCheckpoint
    from models.verification import VerificationRun
    from models.webhook import WebhookDelivery
    from models.runtime import WorkerHeartbeat
    from datetime import datetime, timedelta, timezone

    db = SessionLocal()
    try:
        gauges = {
            "agenticops_execution_jobs_running": float(db.query(ExecutionJob.id).filter(ExecutionJob.status == "running").count()),
            "agenticops_webhook_deliveries_pending": float(db.query(WebhookDelivery.id).filter(WebhookDelivery.status.in_(["pending", "retry", "delivering"])).count()),
            "agenticops_webhook_deliveries_dead": float(db.query(WebhookDelivery.id).filter(WebhookDelivery.status == "dead").count()),
            "agenticops_verifications_pending": float(db.query(VerificationRun.id).filter(VerificationRun.status.in_(["pending", "checking"])).count()),
            "agenticops_elk_checkpoint_lag_seconds": float(db.query(func.coalesce(func.max(IngestionCheckpoint.lag_seconds), 0)).scalar() or 0),
            "agenticops_worker_alive": float(
                bool(
                    db.query(WorkerHeartbeat.worker_name).filter(
                        WorkerHeartbeat.last_seen_at >= datetime.now(timezone.utc) - timedelta(minutes=2),
                        WorkerHeartbeat.status.in_(["healthy", "degraded"]),
                    ).first()
                )
            ),
        }
        return metrics_registry.render(gauges)
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
