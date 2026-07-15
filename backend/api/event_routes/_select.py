from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter

from api.events import router as legacy_router


def selected_router(predicate: Callable[[str, set[str]], bool]) -> APIRouter:
    router = APIRouter()
    for route in legacy_router.routes:
        methods = set(getattr(route, "methods", set()) or set())
        if predicate(getattr(route, "path", ""), methods):
            router.routes.append(route)
    return router
