import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api import assets as assets_api
from api import alerts as alerts_api
from api import logs as logs_api
from models.automation import Base, AlertEvent, Site
from utils.cache import netbox_cache


class FakeResult:
    def __init__(self, success=True, data=None, error=""):
        self.success = success
        self.data = data or {}
        self.error = error


class CoreApiContractsTest(unittest.IsolatedAsyncioTestCase):
    async def test_assets_clear_cache_is_prefix_scoped(self):
        netbox_cache.set("devices", {"a": 1}, {"ok": True})
        netbox_cache.set("alerts", {"a": 1}, {"should_stay": True})

        await assets_api.clear_cache()

        self.assertIsNone(netbox_cache.get("devices", {"a": 1}))
        self.assertEqual(netbox_cache.get("alerts", {"a": 1}), {"should_stay": True})
        netbox_cache.clear()

    async def test_alerts_severity_zero_is_forwarded(self):
        captured = {}
        original = alerts_api.zabbix_mcp.execute

        async def fake_execute(params):
            captured.update(params)
            return FakeResult(data={"count": 0, "alerts": []})

        alerts_api.zabbix_mcp.execute = fake_execute
        try:
            await alerts_api.get_alerts(severity=0, limit=10)
            self.assertIn("severity", captured)
            self.assertEqual(captured["severity"], 0)
        finally:
            alerts_api.zabbix_mcp.execute = original

    async def test_logs_clear_cache_is_prefix_scoped(self):
        netbox_cache.set("logs", {"a": 1}, {"ok": True})
        netbox_cache.set("alerts", {"a": 1}, {"should_stay": True})

        await logs_api.clear_cache()

        self.assertIsNone(netbox_cache.get("logs", {"a": 1}))
        self.assertEqual(netbox_cache.get("alerts", {"a": 1}), {"should_stay": True})
        netbox_cache.clear()

    async def test_alert_event_lifecycle(self):
        engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine, tables=[Site.__table__, AlertEvent.__table__])
        db = TestingSessionLocal()
        try:
            created = await alerts_api.create_alert_event(
                alerts_api.AlertEventCreateRequest(
                    source="AUTOMATION",
                    name="unit-test-alert",
                    severity="warning",
                    severity_level=2,
                    host="10.0.0.1",
                    occurred_at=datetime.now(),
                ),
                db=db,
            )
            self.assertEqual(created.status, "open")

            listed = await alerts_api.list_alert_events(limit=10, skip=0, db=db)
            self.assertEqual(listed["page"].total, 1)
            self.assertEqual(len(listed["events"]), 1)

            acked = await alerts_api.acknowledge_alert_event(created.id, db=db)
            self.assertTrue(acked.acknowledged)
            self.assertEqual(acked.status, "acknowledged")

            resolved = await alerts_api.resolve_alert_event(created.id, db=db)
            self.assertEqual(resolved.status, "resolved")
            self.assertIsNotNone(resolved.resolved_at)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
