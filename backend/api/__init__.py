from .assets import router as assets_router
from .logs import router as logs_router
from .models import router as models_router
from .automation import router as automation_router
from .ssh_management import router as ssh_management_router
from .command_templates import router as command_templates_router
from .events import router as events_router
from .tickets import router as tickets_router
from .cases import router as cases_router
from .agents import router as agents_router
from .memories import router as memories_router
from .fabric import router as fabric_router

__all__ = [
    "assets_router",
    "logs_router",
    "models_router",
    "automation_router",
    "ssh_management_router",
    "command_templates_router",
    "events_router",
    "tickets_router",
    "cases_router",
    "agents_router",
    "memories_router",
    "fabric_router",
]
