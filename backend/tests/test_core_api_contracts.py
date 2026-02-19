import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api import assets as assets_api
from api import events as events_api
from api import logs as logs_api
from config.settings import settings
from models.automation import Base, AlertEvent, AutomationTask, Site
from services.execution_engine import ExecutionEngine, ExecutionStatus, Executor, ExecutorType
from utils.cache import netbox_cache


class CoreApiContractsTest(unittest.IsolatedAsyncioTestCase):
    async def test_assets_clear_cache_is_prefix_scoped(self):
        netbox_cache.set("devices", {"a": 1}, {"ok": True})
        netbox_cache.set("alerts", {"a": 1}, {"should_stay": True})

        await assets_api.clear_cache()

        self.assertIsNone(netbox_cache.get("devices", {"a": 1}))
        self.assertEqual(netbox_cache.get("alerts", {"a": 1}), {"should_stay": True})
        netbox_cache.clear()

    async def test_event_ingest_and_list(self):
        engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine, tables=[Site.__table__, AlertEvent.__table__])
        db = TestingSessionLocal()
        try:
            event = await events_api.ingest_event(
                events_api.EventIngestRequest(
                    source="SPLUNK",
                    event_type="interface_down",
                    name="unit-test-event",
                    severity="warning",
                    severity_level=2,
                    host="10.0.0.1",
                    occurred_at=datetime.now(),
                ),
                db=db,
            )
            self.assertTrue(event["accepted"])

            listed = await events_api.list_events(limit=10, skip=0, db=db)
            self.assertEqual(listed["page"].total, 1)
            self.assertEqual(len(listed["events"]), 1)
        finally:
            db.close()

    async def test_logs_clear_cache_is_prefix_scoped(self):
        netbox_cache.set("logs", {"a": 1}, {"ok": True})
        netbox_cache.set("alerts", {"a": 1}, {"should_stay": True})

        await logs_api.clear_cache()

        self.assertIsNone(netbox_cache.get("logs", {"a": 1}))
        self.assertEqual(netbox_cache.get("alerts", {"a": 1}), {"should_stay": True})
        netbox_cache.clear()

    async def test_event_ticket_mock_mode(self):
        engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine, tables=[Site.__table__, AlertEvent.__table__])
        db = TestingSessionLocal()
        try:
            created = await events_api.ingest_event(
                events_api.EventIngestRequest(
                    source="SPLUNK",
                    event_type="neighbor_down",
                    name="unit-test-ticket-event",
                    severity="high",
                    severity_level=4,
                    host="10.0.0.2",
                    occurred_at=datetime.now(),
                ),
                db=db,
            )
            record = created["event"]
            ticket = await events_api.create_event_ticket(record.id, events_api.EventTicketCreateRequest(), db=db)
            self.assertTrue(ticket["success"])
            self.assertTrue(str(ticket.get("ticket_id", "")).startswith("LOCAL-"))

            relations = await events_api.get_event_relations(record.id, db=db)
            self.assertEqual(relations["event_id"], record.id)
            self.assertIn("ticket", relations)
        finally:
            db.close()

    async def test_event_relations_status_flow(self):
        engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(
            bind=engine,
            tables=[Site.__table__, AlertEvent.__table__, AutomationTask.__table__],
        )
        db = TestingSessionLocal()
        try:
            site = Site(id=1, site_code="SZ", site_name="Shenzhen")
            db.add(site)
            db.commit()

            created = await events_api.ingest_event(
                events_api.EventIngestRequest(
                    source="SPLUNK",
                    event_type="interface_down",
                    name="unit-test-relations-flow",
                    severity="warning",
                    severity_level=2,
                    host="10.0.0.10",
                    site_id=1,
                    occurred_at=datetime.now(),
                ),
                db=db,
            )
            event_id = created["event"].id
            now = datetime.now()

            t_old = AutomationTask(
                task_code="TASK_REL_OLD",
                site_id=1,
                status="waiting_confirm",
                triggered_by="event",
                trigger_event={"source_type": "AlertEvent", "source_id": event_id},
                created_at=now.replace(microsecond=0),
            )
            t_mid = AutomationTask(
                task_code="TASK_REL_MID",
                site_id=1,
                status="running",
                triggered_by="event",
                trigger_event={"source_type": "AlertEvent", "source_id": event_id},
                created_at=now.replace(microsecond=0),
            )
            t_new = AutomationTask(
                task_code="TASK_REL_NEW",
                site_id=1,
                status="success",
                triggered_by="event",
                trigger_event={"source_type": "AlertEvent", "source_id": event_id},
                created_at=now,
            )
            t_other = AutomationTask(
                task_code="TASK_REL_OTHER",
                site_id=1,
                status="failed",
                triggered_by="event",
                trigger_event={"source_type": "AlertEvent", "source_id": event_id + 999},
                created_at=now,
            )
            db.add_all([t_old, t_mid, t_new, t_other])
            db.commit()

            relations = await events_api.get_event_relations(event_id, db=db)
            linked = relations["linked_tasks"]
            self.assertEqual(relations["event_id"], event_id)
            self.assertEqual(len(linked), 3)
            self.assertEqual({item["status"] for item in linked}, {"waiting_confirm", "running", "success"})
            self.assertNotIn(t_other.id, [item["task_id"] for item in linked])

            db.query(AutomationTask).filter(AutomationTask.id == t_mid.id).update({"status": "success"})
            db.commit()
            updated_relations = await events_api.get_event_relations(event_id, db=db)
            updated_status = {item["task_id"]: item["status"] for item in updated_relations["linked_tasks"]}
            self.assertEqual(updated_status.get(t_mid.id), "success")
        finally:
            db.close()

    async def test_observe_only_blocks_non_readonly_actions(self):
        class DummyScriptExecutor(Executor):
            def __init__(self):
                super().__init__(ExecutorType.SCRIPT)
                self.executed = 0

            async def execute(self, task_id, action_config, context):
                self.executed += 1
                return {"status": "success", "message": f"task-{task_id}-ok"}

            def validate_config(self, action_config):
                return True

        engine = ExecutionEngine()
        executor = DummyScriptExecutor()
        engine.register_executor(executor)

        original = settings.automation_observe_only
        settings.automation_observe_only = True
        try:
            blocked = await engine.execute_action(
                task_id=1001,
                action_type=ExecutorType.SCRIPT,
                action_config={},
                context={},
            )
            self.assertEqual(blocked.status, ExecutionStatus.ABORTED)
            self.assertEqual(executor.executed, 0)

            allowed = await engine.execute_action(
                task_id=1002,
                action_type=ExecutorType.SCRIPT,
                action_config={"read_only": True},
                context={},
            )
            self.assertEqual(allowed.status, ExecutionStatus.SUCCESS)
            self.assertEqual(executor.executed, 1)
        finally:
            settings.automation_observe_only = original


if __name__ == "__main__":
    unittest.main()
