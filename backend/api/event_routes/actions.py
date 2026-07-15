from api.event_routes._select import selected_router


_RESERVED = {
    "/api/events/mode",
    "/api/events/ingest",
    "/api/events",
    "/api/events/clusters",
    "/api/events/root-cause-candidates",
}

router = selected_router(lambda path, methods: path not in _RESERVED and not path.endswith("/relations"))
