# Migration 0011: Multi-Agent Graph

## Upgrade

Back up PostgreSQL, keep `AUTOMATION_OBSERVE_ONLY=True`, then run:

```bash
cd backend
alembic upgrade head
alembic check
```

Migration `0011_multi_agent_graph` adds graph, task, message, tool-call, budget, checkpoint, timeline, state-transition and hypothesis tables; links AgentRun and EvidenceItem to graph artifacts; and extends the existing Case status enum. It does not delete or rewrite existing Case, Evidence, Claim, approval, plan, execution or verification rows. Old Case status values remain readable.

After upgrade, start the API and Worker together. The API only accepts jobs; `backend/worker.py` advances them.

## Verification

```bash
RUN_POSTGRES_TESTS=1 pytest tests/integration
alembic check
```

Check `/health/ready`, create a non-production Case, call `POST /api/cases/{id}/run-agents`, and confirm the Graph Run moves from `queued` while Timeline and budget endpoints return persisted data.

## Rollback

Stop API and Worker before downgrade:

```bash
cd backend
alembic downgrade 0010
```

Downgrade removes only the new graph tables and links. PostgreSQL Case enum values are intentionally retained because deleting enum values is destructive. Export graph Timeline, messages, hypotheses and checkpoints first if they must be retained. Existing Evidence, Claims, Plans and legacy Case records are not intentionally deleted, but move active Cases through the state service to a legacy-compatible state before running an older application version.

Do not downgrade while a Graph Run is active. A database restore is the production rollback path if post-upgrade writes must be preserved exactly.
