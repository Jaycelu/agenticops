# Backend test structure

The production-hardening test suite is split by dependency boundary:

- `unit/`: deterministic tests that do not connect to external services.
- `integration/`: tests that require a real PostgreSQL instance.
- `contract/`: provider and adapter contract tests added with each integration.
- `e2e/`: full event-to-verification scenarios added once the worker boundary exists.
- `fixtures/`: sanitized replay datasets and reusable payloads.

Integration tests are skipped by default. Run them explicitly with:

```bash
RUN_POSTGRES_TESTS=1 pytest -m integration
```

Unit tests must not depend on SQLite as a substitute for PostgreSQL behavior. Database
state-machine, JSON, enum, locking, idempotency, migration, and outbox tests belong in
`integration/` and run against PostgreSQL 16 in CI.

Tests should assert safety properties and observable behavior rather than private method
structure. Every production incident or escaped regression must add a replay fixture or a
focused regression test before the fix is accepted.
