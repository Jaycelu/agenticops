from __future__ import annotations

from pathlib import Path

import pytest

from api.errors import error_payload
from observability.metrics import MetricsRegistry


pytestmark = pytest.mark.unit
BACKEND = Path(__file__).resolve().parents[2]


def test_error_envelope_keeps_compatibility_detail() -> None:
    payload = error_payload("validation_error", "invalid request", [{"field": "name"}])

    assert payload["detail"] == "invalid request"
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["details"] == [{"field": "name"}]
    assert "request_id" in payload["error"]


def test_metrics_registry_renders_escaped_labels_and_gauges() -> None:
    registry = MetricsRegistry()
    registry.increment("requests_total", method="GET", route='/api/\"events')

    output = registry.render({"worker_alive": 1})

    assert '# TYPE requests_total counter' in output
    assert 'route="/api/\\\"events"' in output
    assert "# TYPE worker_alive gauge\nworker_alive 1" in output


def test_api_runtime_does_not_start_background_work() -> None:
    main_source = (BACKEND / "main.py").read_text()
    worker_source = (BACKEND / "worker.py").read_text()

    assert "create_task(" not in main_source
    assert "webhook_worker.run_once" not in main_source
    assert "ingestion_worker.run_once" not in main_source
    assert "webhook_worker.run_once" in worker_source
    assert "ingestion_worker.run_once" in worker_source
    assert "verification_service.run_due_once" in worker_source


def test_event_route_composition_preserves_every_public_route() -> None:
    from api.event_routes import router as composed_router
    from api.events import router as legacy_router

    def contract(router):
        rows = set()
        for route in router.routes:
            nested = getattr(route, "original_router", None)
            if nested is not None:
                rows.update(contract(nested))
            elif getattr(route, "path", "").startswith("/api/events"):
                rows.add((route.path, tuple(sorted(getattr(route, "methods", set()) or set()))))
        return rows

    assert contract(composed_router) == contract(legacy_router)
