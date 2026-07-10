from __future__ import annotations

import os

import pytest


DEFAULT_TEST_DATABASE_URL = "postgresql://netops:netops@127.0.0.1:55432/netops_agenticops_test"

# Settings are instantiated during module import. Supply safe test defaults before
# production modules are imported by individual test files.
os.environ.setdefault("APP_SECRET_KEY", "pytest-only-secret")
os.environ.setdefault("DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
os.environ.setdefault("AUTOMATION_DATABASE_URL", os.environ["DATABASE_URL"])
os.environ.setdefault("AUTOMATION_OBSERVE_ONLY", "true")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.getenv("RUN_POSTGRES_TESTS") == "1":
        return

    skip_postgres = pytest.mark.skip(reason="set RUN_POSTGRES_TESTS=1 to run PostgreSQL integration tests")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_postgres)
