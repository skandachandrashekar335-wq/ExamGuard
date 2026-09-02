from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.hall_ticket import (
    HallTicketCreate,
    HallTicketListResponse,
    HallTicketResponse,
    HallTicketUpdate,
)
from app.services import hall_ticket as ht_service

router = APIRouter(prefix="/hall-tickets", tags=["Hall Tickets"])


@router.post(
    "",
    response_model=HallTicketResponse,
    status_code=201,
    summary="Create a hall ticket for an exam registration",
)
def create_hall_ticket(
    data: HallTicketCreate,
    db: Session = Depends(get_db),
):
    try:
        return ht_service.create_hall_ticket(db, data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get(
    "",
    response_model=HallTicketListResponse,
    summary="List hall tickets with optional filters",
)
def list_hall_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    exam_registration_id: int | None = Query(None, description="Filter by registration ID"),
    status: str | None = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
):
    result = ht_service.list_hall_tickets(
        db,
        page=page,
        page_size=page_size,
        exam_registration_id=exam_registration_id,
        status=status,
    )
    return HallTicketListResponse(
        items=[HallTicketResponse.model_validate(ht) for ht in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get(
    "/{hall_ticket_id}",
    response_model=HallTicketResponse,
    summary="Get a hall ticket by ID",
)
def get_hall_ticket(
    hall_ticket_id: int,
    db: Session = Depends(get_db),
):
    ht = ht_service.get_hall_ticket(db, hall_ticket_id)
    if not ht:
        raise HTTPException(status_code=404, detail="Hall ticket not found")
    return ht


@router.get(
    "/by-registration/{exam_registration_id}",
    response_model=HallTicketResponse,
    summary="Get a hall ticket by exam registration ID",
)
def get_hall_ticket_by_registration(
    exam_registration_id: int,
    db: Session = Depends(get_db),
):
    ht = ht_service.get_hall_ticket_by_registration(db, exam_registration_id)
    if not ht:
        raise HTTPException(
            status_code=404,
            detail=f"No hall ticket found for registration {exam_registration_id}",
        )
    return ht


@router.patch(
    "/{hall_ticket_id}",
    response_model=HallTicketResponse,
    summary="Update a hall ticket (status, linked resources)",
)
def update_hall_ticket(
    hall_ticket_id: int,
    data: HallTicketUpdate,
    db: Session = Depends(get_db),
):
    try:
        return ht_service.update_hall_ticket(db, hall_ticket_id, data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
