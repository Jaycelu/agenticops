from .assets import router as assets_router
from .logs import router as logs_router
from .compat import router as compat_router
from .settings import router as settings_router
from .sites import router as sites_router
from .ssh_management import router as ssh_management_router
from .events import router as events_router
from .tickets import router as tickets_router
from .cases import router as cases_router
from .agents import router as agents_router
from .memories import router as memories_router
from .fabric import router as fabric_router
from .zabbix import router as zabbix_router
from .auth import router as auth_router
from .identity_admin import router as identity_admin_router
from .probes import router as probes_router
from .webhooks import router as webhooks_router
from .ingestion import router as ingestion_router

__all__ = [
    "assets_router",
    "logs_router",
    "compat_router",
    "settings_router",
    "sites_router",
    "ssh_management_router",
    "events_router",
    "tickets_router",
    "cases_router",
    "agents_router",
    "memories_router",
    "fabric_router",
    "zabbix_router",
    "auth_router",
    "identity_admin_router",
    "probes_router",
    "webhooks_router",
    "ingestion_router",
]
