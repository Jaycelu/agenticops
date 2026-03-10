# AgenticOps

> An AgenticOps workspace for network operations built around NetBox, ELK, Zabbix, multi-agent analysis, execution workflows, and operational memory.

[简体中文 README](./README.md)

## Overview

AgenticOps is a network operations platform that normalizes signals from infrastructure systems into a single workflow:

`Event -> Case -> Multi-Agent -> Memory -> Fabric`

It is designed to reduce alert noise, improve triage quality, accelerate MTTR, and keep execution plus historical knowledge in one place.

## Key Capabilities

- Unified event center for deduplication, clustering, correlation, and routing
- Case workspace for evidence, agent output, and remediation plans
- Four built-in agents:
  - `Alert Triage Agent`
  - `Historical Analysis Agent`
  - `Insight Analysis Agent`
  - `Autonomous Remediation Agent`
- Memory center for episode, pattern, and outcome reuse
- Execution center for remediation plans and run history
- Source-oriented workspaces for assets, logs, Zabbix, tickets, and settings

## Screenshot

<img src="./agenticops.jpg" alt="AgenticOps overview" width="100%">

## Quick Start

### Requirements

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
python3 main.py
```

Backend endpoints:

- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend endpoint:

- Web UI: `http://localhost:5173`

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
netops_bs/
├── backend/
├── frontend/
├── deploy/
├── docs/
└── agenticops.jpg
```

## Release Notes

The current runtime stack is `Vue 3 + Vite` on the frontend and `FastAPI + PostgreSQL` on the backend.

Before making the repository public, sanitize sample configs, logs, screenshots, and historical docs that may still contain internal addresses, tokens, or production-like data.
