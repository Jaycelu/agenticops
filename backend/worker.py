from __future__ import annotations

import asyncio
import os
import signal
import socket
import time
from datetime import datetime, timezone

from loguru import logger

from auth.session_service import auth_secret_bytes
from config.logging import setup_logging
from database import SessionLocal, init_db
from ingestion.worker import ingestion_worker
from models.runtime import WorkerHeartbeat
from services.embedding_service import backfill_memory_embeddings, build_embedder
from utils.cache import netbox_cache
from verifications.service import verification_service
from webhooks.worker import webhook_worker


setup_logging()


class RuntimeWorker:
    def __init__(self) -> None:
        self.name = f"{socket.gethostname()}:{os.getpid()}"
        self.stop_event = asyncio.Event()
        self.last_retention = 0.0
        self.last_embedding = 0.0
        self.last_cache_cleanup = 0.0

    async def run(self) -> None:
        init_db()
        auth_secret_bytes()
        self._install_signals()
        logger.bind(worker_name=self.name).info("worker_started")
        while not self.stop_event.is_set():
            cycle = {"webhook": 0, "ingestion": 0, "verification": 0}
            try:
                for _ in range(20):
                    if not await asyncio.to_thread(webhook_worker.run_once):
                        break
                    cycle["webhook"] += 1
                if await ingestion_worker.run_once():
                    cycle["ingestion"] += 1
                if await verification_service.run_due_once():
                    cycle["verification"] += 1
                await self._maintenance()
                self._heartbeat("healthy", cycle)
            except Exception as exc:
                logger.bind(worker_name=self.name, error_type=type(exc).__name__).exception("worker_cycle_failed")
                self._heartbeat("degraded", {**cycle, "error_type": type(exc).__name__})
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=1.0 if any(cycle.values()) else 5.0)
            except TimeoutError:
                pass
        self._heartbeat("stopped", {})
        logger.bind(worker_name=self.name).info("worker_stopped")

    async def _maintenance(self) -> None:
        now = time.monotonic()
        if now - self.last_cache_cleanup >= 60:
            netbox_cache.cleanup_expired()
            self.last_cache_cleanup = now
        if now - self.last_retention >= 12 * 3600:
            from services.data_retention_service import data_retention_service

            await asyncio.to_thread(data_retention_service.cleanup)
            self.last_retention = now
        if now - self.last_embedding >= 3600 and getattr(build_embedder(), "is_enabled", False):
            db = SessionLocal()
            try:
                await backfill_memory_embeddings(db, limit=200)
                db.commit()
            finally:
                db.close()
            self.last_embedding = now

    def _heartbeat(self, status: str, details: dict) -> None:
        db = SessionLocal()
        try:
            row = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.worker_name == self.name).first()
            if row is None:
                row = WorkerHeartbeat(worker_name=self.name, status=status, details=details)
                db.add(row)
            else:
                row.status = status
                row.details = details
                row.last_seen_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()

    def _install_signals(self) -> None:
        loop = asyncio.get_running_loop()
        for name in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(name, self.stop_event.set)
            except NotImplementedError:
                pass


def main() -> None:
    asyncio.run(RuntimeWorker().run())


if __name__ == "__main__":
    main()
