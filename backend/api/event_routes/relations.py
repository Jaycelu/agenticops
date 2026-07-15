from api.event_routes._select import selected_router


router = selected_router(lambda path, methods: path.endswith("/relations"))
