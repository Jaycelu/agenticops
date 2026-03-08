"""
将旧 alert_event / automation_task* 表迁移归档并从主运行库退场。

默认行为：
1. 先执行 AutomationTask -> AgenticOps 的补迁
2. 解除 local_ticket.event_id 对 alert_event 的外键
3. 将旧表重命名为 archived__<table>

可选行为：
- --drop: 在补迁完成后直接 DROP 旧表，而不是归档重命名
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import engine, init_db
from scripts.backfill_agenticops_data import run as run_backfill


LEGACY_TABLES = [
    "alert_event",
    "automation_action_log",
    "automation_approval",
    "automation_task_feedback",
    "automation_task",
]


def _table_exists(conn, table_name: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = current_schema()
                      AND table_name = :table_name
                )
                """
            ),
            {"table_name": table_name},
        ).scalar()
    )


def _archive_or_drop_tables(
    *,
    tables: Iterable[str],
    archive_prefix: str,
    drop: bool,
    dry_run: bool,
) -> list[dict]:
    results: list[dict] = []
    with engine.begin() as conn:
        for table_name in tables:
            if not _table_exists(conn, table_name):
                results.append({"table": table_name, "action": "skip_missing"})
                continue

            if drop:
                statement = f'DROP TABLE IF EXISTS "{table_name}" CASCADE'
                action = "drop"
            else:
                archived_name = f"{archive_prefix}{table_name}"
                if _table_exists(conn, archived_name):
                    statement = f'DROP TABLE IF EXISTS "{archived_name}" CASCADE'
                    if not dry_run:
                        conn.execute(text(statement))
                    results.append({"table": archived_name, "action": "drop_existing_archive"})
                statement = f'ALTER TABLE "{table_name}" RENAME TO "{archived_name}"'
                action = f"rename_to:{archived_name}"

            if not dry_run:
                conn.execute(text(statement))
            results.append({"table": table_name, "action": action})
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Retire legacy automation schema")
    parser.add_argument("--archive-prefix", default="archived__", help="Prefix for renamed legacy tables")
    parser.add_argument("--drop", action="store_true", help="Drop legacy tables instead of renaming them")
    parser.add_argument("--skip-backfill", action="store_true", help="Skip AutomationTask -> AgenticOps backfill")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without executing DDL")
    parser.add_argument("--limit", type=int, default=None, help="Optional legacy task backfill limit")
    args = parser.parse_args()

    try:
        init_db()
        with engine.begin() as conn:
            existing_tables = [table for table in LEGACY_TABLES if _table_exists(conn, table)]
        if not args.skip_backfill and "automation_task" in existing_tables:
            run_backfill(limit=args.limit, dry_run=args.dry_run)
        operations = _archive_or_drop_tables(
            tables=existing_tables,
            archive_prefix=args.archive_prefix,
            drop=args.drop,
            dry_run=args.dry_run,
        )
        print(
            {
                "dry_run": bool(args.dry_run),
                "drop": bool(args.drop),
                "archive_prefix": args.archive_prefix,
                "operations": operations,
            }
        )
    except SQLAlchemyError as exc:
        raise SystemExit(f"Schema retirement failed: {exc}") from exc


if __name__ == "__main__":
    main()
