"""Ticket CRUD endpoints."""

from fastapi import APIRouter, Depends

from app.schemas.ticket import TicketCreate, TicketResponse, TicketStatusUpdate

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("/", response_model=TicketResponse)
async def create_ticket(payload: TicketCreate):
    raise NotImplementedError("Create ticket not yet implemented")


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: int):
    raise NotImplementedError("Get ticket not yet implemented")


@router.patch("/{ticket_id}/status")
async def update_ticket_status(ticket_id: int, payload: TicketStatusUpdate):
    raise NotImplementedError("Update ticket status not yet implemented")
