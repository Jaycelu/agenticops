from api.event_routes._select import selected_router


router = selected_router(
    lambda path, methods: path in {"/api/events/clusters", "/api/events/root-cause-candidates"}
)
