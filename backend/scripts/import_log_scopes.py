"""
从 JSON 文件导入日志范围配置。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from database import SessionLocal, init_db
from models.log_scope import LogScope
from services.log_scope_service import log_scope_service


def import_scopes(file_path: Path, *, replace: bool) -> None:
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    scopes = payload.get("scopes") if isinstance(payload, dict) else payload
    if not isinstance(scopes, list):
        raise ValueError("input JSON must be a list or {'scopes': [...]}")

    init_db()
    db = SessionLocal()
    try:
        for item in scopes:
            scope_key = str(item.get("scope_key") or "").strip()
            if not scope_key:
                raise ValueError("scope_key is required")
            existing = db.query(LogScope).filter(LogScope.scope_key == scope_key).first()
            if existing:
                if replace:
                    log_scope_service.update_scope(db, existing.id, item)
                    print(f"updated: {scope_key}")
                else:
                    print(f"skipped: {scope_key}")
                continue
            created = log_scope_service.create_scope(db, item)
            print(f"created: {created['scope_key']}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import ELK log scopes from JSON.")
    parser.add_argument("file", help="Path to JSON file")
    parser.add_argument("--replace", action="store_true", help="Replace existing scopes with the same scope_key")
    args = parser.parse_args()
    import_scopes(Path(args.file), replace=args.replace)


if __name__ == "__main__":
    main()
