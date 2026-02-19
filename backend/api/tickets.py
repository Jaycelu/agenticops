from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.schemas.common import PageMeta
from api.schemas.tickets import (
    LocalTicketListResponse,
    LocalTicketUpdateRequest,
    LocalTicketUpdateResponse,
)
from database import get_db
from models.automation import LocalTicket

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _to_ticket_item(ticket: LocalTicket):
    return {
        "id": ticket.id,
        "ticket_code": ticket.ticket_code,
        "provider": ticket.provider,
        "event_id": ticket.event_id,
        "title": ticket.title,
        "description": ticket.description,
        "priority": ticket.priority,
        "requester": ticket.requester,
        "status": ticket.status,
        "metadata": ticket.ticket_metadata or {},
        "closed_at": ticket.closed_at,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
    }


@router.get("", response_model=LocalTicketListResponse)
async def list_tickets(
    status: Optional[str] = None,
    event_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query = db.query(LocalTicket)
    if status:
        query = query.filter(LocalTicket.status == status)
    if event_id is not None:
        query = query.filter(LocalTicket.event_id == event_id)

    total = query.count()
    records = query.order_by(LocalTicket.created_at.desc()).offset(skip).limit(limit).all()
    returned = len(records)
    return {
        "page": PageMeta(
            total=total,
            skip=skip,
            limit=limit,
            returned=returned,
            has_more=(skip + returned) < total,
        ),
        "tickets": [_to_ticket_item(r) for r in records],
    }


@router.get("/{ticket_code}")
async def get_ticket(ticket_code: str, db: Session = Depends(get_db)):
    ticket = db.query(LocalTicket).filter(LocalTicket.ticket_code == ticket_code).first()
    if not ticket:
        return {"success": False, "message": "Ticket not found", "ticket": None}
    return {"success": True, "message": "ok", "ticket": _to_ticket_item(ticket)}


@router.patch("/{ticket_code}", response_model=LocalTicketUpdateResponse)
async def update_ticket_status(
    ticket_code: str,
    payload: LocalTicketUpdateRequest,
    db: Session = Depends(get_db),
):
    ticket = db.query(LocalTicket).filter(LocalTicket.ticket_code == ticket_code).first()
    if not ticket:
        return {"success": False, "message": "Ticket not found", "ticket": None}

    status = (payload.status or "").strip().lower()
    allowed = {"open", "in_progress", "resolved", "closed"}
    if status not in allowed:
        return {"success": False, "message": "Invalid status", "ticket": ticket}

    previous_status = ticket.status
    ticket.status = status
    meta = ticket.ticket_metadata or {}
    history = meta.get("status_history") or []
    history.append(
        {
            "from_status": previous_status,
            "to_status": status,
            "operator": payload.operator or "operator",
            "comment": payload.comment or "",
            "updated_at": datetime.now().isoformat(),
        }
    )
    meta["status_history"] = history
    ticket.ticket_metadata = meta
    if status in {"resolved", "closed"}:
        ticket.closed_at = datetime.now()
    db.commit()
    db.refresh(ticket)
    return {"success": True, "message": "Ticket updated", "ticket": _to_ticket_item(ticket)}
