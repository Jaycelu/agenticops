# AgenticOps

> Network operations system for NetBox, ELK, Zabbix, multi-agent analysis, execution workflows, and operational memory.

[简体中文 README](./README.md)

## Overview

AgenticOps normalizes infrastructure signals into a single workflow:

`Event -> Case -> Multi-Agent -> Memory -> Fabric / Execution`

## Key Capabilities

- Unified event center for deduplication, clustering, correlation, and routing
- Case workspace for evidence, agent output, and remediation plans
- Five built-in agents:
  - `Alert Triage Agent`
  - `Historical Analysis Agent`
  - `Insight Analysis Agent`
  - `Autonomous Remediation Agent`
  - `Safety Critic Agent`
- Memory center for episode, pattern, and outcome reuse
- Execution center for remediation plans and run history
- Local/OIDC/LDAP/SAML authentication, RBAC, frozen approvals, and immutable audit records
- Guarded read-only device probes, generic signed webhooks, durable ELK ingestion, and post-change verification
- Source-oriented workspaces for assets, logs, Zabbix, tickets, and settings

Case diagnosis now runs as a durable asynchronous graph. The Supervisor creates conditional tasks from evidence and budget state; strict Evidence Requests pass through Tool Registry, PolicyGuard and Probe Gateway; an independent Diagnostic Critic searches for counter-evidence; and the Worker recovers expired leases from checkpoints. The graph still stops after Safety Review in Observe-only mode and never autonomously performs a device change. See [Multi-Agent Diagnostic Architecture](./docs/MULTI_AGENT_DIAGNOSTIC_ARCHITECTURE.md) and [Migration 0011](./docs/MIGRATION_0011_MULTI_AGENT_GRAPH.md).

## Screenshot

<img src="./agenticops.jpg" alt="AgenticOps overview" width="100%">

## Quick Start

### Docker Compose

Compose starts one PostgreSQL database, a one-shot migration job, backend API, background worker, and frontend Web.

```bash
cp deploy/docker.env.example .env
# Replace APP_SECRET_KEY, POSTGRES_PASSWORD, AUTH_PUBLIC_BASE_URL, and FRONTEND_URL.
docker compose config -q
docker compose build
docker compose up -d postgres
docker compose run --rm migrate
docker compose up -d backend worker frontend
```

Endpoints:

- Web UI: `http://localhost:5173`
- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health/ready`

Services:

| Service | Container | Port |
| --- | --- | --- |
| PostgreSQL | `agenticops-postgres` | `5432` |
| Migration | `agenticops-migrate` | one-shot job |
| Backend | `agenticops-backend` | `8000` |
| Worker | `agenticops-worker` | no public port |
| Frontend | `agenticops-frontend` | `5173` |

Keep `AUTOMATION_OBSERVE_ONLY=True` during initial deployment and the 14-day shadow period. Production also requires an HTTPS reverse proxy; Compose does not issue TLS certificates. See [DEPLOYMENT.md](./DEPLOYMENT.md) for the complete installation and upgrade procedure.

```bash
docker compose down
```

### Local Development

Requirements:

- Python `3.11+`
- Node.js `18+`
- PostgreSQL `14+`
- Reachable `NetBox / ELK / Zabbix / LLM API`

### Backend

```bash
cp deploy/env.example backend/.env
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --host 0.0.0.0 --port 8000
# Start `python -m worker` in a second terminal.
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Main Modules

| Module | Route | Purpose |
| --- | --- | --- |
| Dashboard | `/` | Platform overview across cases, agents, and memories |
| Events | `/events` | Unified event entry, clustering, and root-cause candidates |
| Cases | `/cases` | Evidence, agent conclusions, and remediation planning |
| Fabric | `/fabric` | Remediation plan execution and run history |
| Agents | `/agents` | Agent catalog and health status |
| Memories | `/memories` | Episode / pattern / outcome management |
| Logs | `/logs` | Log search and aggregation |
| Zabbix | `/zabbix` | Alert and host status view |
| Assets | `/assets` | Device, IP, rack, VLAN, and prefix context |
| Tickets | `/tickets` | Human handoff and tracking |
| Settings | `/settings` | Integrations, model setup, and SSH channels |

## Project Structure

```text
agenticops/
├── backend/
├── frontend/
├── deploy/
├── docs/
└── agenticops.jpg
```

## Runtime Stack

- Frontend: `Vue 3 + Vite + Nginx`
- Backend: `FastAPI + PostgreSQL`
- Compose: PostgreSQL, migration, backend API, worker, frontend
