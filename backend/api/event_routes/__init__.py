"""Event API composition split by responsibility.

The handler functions remain reusable from ``api.events`` while route ownership is
separated here, allowing each surface to evolve and receive independent policy,
metrics, and tests without a second set of URLs.
"""
from fastapi import APIRouter

from api.event_routes.actions import router as actions_router
from api.event_routes.ingestion import router as ingestion_router
from api.event_routes.query import router as query_router
from api.event_routes.relations import router as relations_router
from api.event_routes.statistics import router as statistics_router


router = APIRouter()
router.include_router(ingestion_router)
router.include_router(query_router)
router.include_router(relations_router)
router.include_router(statistics_router)
router.include_router(actions_router)

__all__ = ["router"]
