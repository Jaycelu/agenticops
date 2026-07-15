from __future__ import annotations

from datetime import datetime, timedelta, timezone

from database import SessionLocal
from models.runtime import WorkerHeartbeat


def main() -> int:
    db = SessionLocal()
    try:
        threshold = datetime.now(timezone.utc) - timedelta(minutes=2)
        alive = db.query(WorkerHeartbeat.worker_name).filter(
            WorkerHeartbeat.last_seen_at >= threshold,
            WorkerHeartbeat.status.in_(["healthy", "degraded"]),
        ).first()
        return 0 if alive else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
