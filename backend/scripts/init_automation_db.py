"""Upgrade the automation database to the current Alembic revision."""
import os
import sys

from alembic import command

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_alembic_config, init_db


def main():
    command.upgrade(get_alembic_config(), "head")
    init_db()
    print("[OK] automation database migrated to head")


if __name__ == "__main__":
    main()
