from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from database import get_db
from api.schemas.agents import (
    AgentCatalogItemResponse,
    AgentClaimResponse,
    AgentHealthItemResponse,
    AgentHealthResponse,
    AgentRunListResponse,
    AgentRunResponse,
)
from models.agenticops import AgentClaim, AgentRun, AgentRunStatus, AgentType

router = APIRouter(prefix="/api/agents", tags=["智能体中心"])


AGENT_CATALOG: List[Dict[str, object]] = [
    {
        "agent_type": AgentType.TRIAGE.value,
        "name": "Alert Triage Agent",
        "purpose": "负责告警分类、富化、去重和初步风险判断。",
        "inputs": ["source_event", "log digest", "basic asset context"],
        "outputs": ["triage summary", "priority", "evidence needs"],
    },
    {
        "agent_type": AgentType.HISTORICAL.value,
        "name": "Historical Analysis Agent",
        "purpose": "检索历史案例、成功动作和失败经验。",
        "inputs": ["case summary", "memory entries", "feedback"],
        "outputs": ["similar cases", "recommended actions", "warnings"],
    },
    {
        "agent_type": AgentType.INSIGHT.value,
        "name": "Insight Analysis Agent",
        "purpose": "联合日志、拓扑和 Zabbix 告警进行根因交叉验证，必要时给出执行侧采证建议。",
        "inputs": ["evidence items", "topology", "zabbix alerts"],
        "outputs": ["root cause hypothesis", "impact scope", "confidence"],
    },
    {
        "agent_type": AgentType.REMEDIATION.value,
        "name": "Autonomous Remediation Agent",
        "purpose": "输出修复计划、回滚方案和自动执行门控建议。",
        "inputs": ["agent claims", "execution policy", "safety checks"],
        "outputs": ["remediation draft", "approval need", "rollback plan"],
    },
]


@router.get("/catalog", response_model=list[AgentCatalogItemResponse])
async def get_agent_catalog():
    return [AgentCatalogItemResponse(**item) for item in AGENT_CATALOG]


@router.get("/health", response_model=AgentHealthResponse)
async def get_agent_health(db: Session = Depends(get_db)):
    rows = db.query(
        AgentRun.agent_type,
        func.count(AgentRun.id),
        func.sum(case((AgentRun.status == AgentRunStatus.RUNNING, 1), else_=0)),
        func.sum(case((AgentRun.status == AgentRunStatus.FAILED, 1), else_=0)),
        func.max(AgentRun.started_at),
    ).group_by(AgentRun.agent_type).all()

    row_map = {
        agent_type.value if hasattr(agent_type, "value") else str(agent_type): {
            "total_runs": total or 0,
            "running_runs": running or 0,
            "failed_runs": failed or 0,
            "last_run_at": last_run_at,
        }
        for agent_type, total, running, failed, last_run_at in rows
    }

    items = [
        AgentHealthItemResponse(
            agent_type=item["agent_type"],
            total_runs=int(row_map.get(item["agent_type"], {}).get("total_runs", 0)),
            running_runs=int(row_map.get(item["agent_type"], {}).get("running_runs", 0)),
            failed_runs=int(row_map.get(item["agent_type"], {}).get("failed_runs", 0)),
            last_run_at=row_map.get(item["agent_type"], {}).get("last_run_at"),
        )
        for item in AGENT_CATALOG
    ]
    return AgentHealthResponse(items=items)


@router.get("/runs", response_model=AgentRunListResponse)
async def list_agent_runs(
    case_id: Optional[int] = None,
    agent_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(AgentRun)
    if case_id is not None:
        query = query.filter(AgentRun.case_id == case_id)
    if agent_type:
        query = query.filter(AgentRun.agent_type == agent_type)
    if status:
        query = query.filter(AgentRun.status == status)

    total = query.count()
    items = query.order_by(AgentRun.started_at.desc()).offset(skip).limit(limit).all()
    return AgentRunListResponse(
        total=total,
        items=[
            AgentRunResponse(
                id=item.id,
                case_id=item.case_id,
                agent_type=item.agent_type.value if hasattr(item.agent_type, "value") else str(item.agent_type),
                agent_name=item.agent_name,
                status=item.status.value if hasattr(item.status, "value") else str(item.status),
                input_payload=item.input_payload or {},
                output_payload=item.output_payload or {},
                started_at=item.started_at,
                finished_at=item.finished_at,
                duration_ms=item.duration_ms,
                error_message=item.error_message,
            )
            for item in items
        ],
    )


@router.get("/runs/{run_id}", response_model=AgentRunResponse)
async def get_agent_run(run_id: int, db: Session = Depends(get_db)):
    item = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return AgentRunResponse(
        id=item.id,
        case_id=item.case_id,
        agent_type=item.agent_type.value if hasattr(item.agent_type, "value") else str(item.agent_type),
        agent_name=item.agent_name,
        status=item.status.value if hasattr(item.status, "value") else str(item.status),
        input_payload=item.input_payload or {},
        output_payload=item.output_payload or {},
        started_at=item.started_at,
        finished_at=item.finished_at,
        duration_ms=item.duration_ms,
        error_message=item.error_message,
    )


@router.get("/runs/{run_id}/claims", response_model=list[AgentClaimResponse])
async def get_agent_run_claims(run_id: int, db: Session = Depends(get_db)):
    run = db.query(AgentRun.id).filter(AgentRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    items = db.query(AgentClaim).filter(AgentClaim.agent_run_id == run_id).order_by(AgentClaim.created_at.desc()).all()
    return [
        AgentClaimResponse(
            id=item.id,
            case_id=item.case_id,
            agent_run_id=item.agent_run_id,
            agent_type=item.agent_type.value if hasattr(item.agent_type, "value") else str(item.agent_type),
            claim_type=item.claim_type,
            claim_text=item.claim_text,
            status=item.status.value if hasattr(item.status, "value") else str(item.status),
            confidence=float(item.confidence or 0.0),
            evidence_refs=item.evidence_refs or [],
            gaps=item.gaps or [],
            claim_metadata=item.claim_metadata or {},
            created_at=item.created_at,
        )
        for item in items
    ]
