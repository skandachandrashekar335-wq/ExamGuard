from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import Role, require_role
from app.core.database import get_db
from app.schemas.hall_ticket_seat_mapping import (
    SeatMappingListResponse,
    SeatMappingResponse,
)
from app.services import hall_ticket_seat_mapping as mapping_service

router = APIRouter(prefix="/hall-ticket-mappings", tags=["Hall Ticket Mappings"])


@router.get(
    "/{hall_ticket_id}",
    response_model=SeatMappingResponse,
    summary="Resolve seat assignment from a hall ticket",
)
def get_seat_mapping(
    hall_ticket_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR])),
):
    result = mapping_service.resolve_hall_ticket_seat(db, hall_ticket_id)
    return result


@router.get(
    "",
    response_model=SeatMappingListResponse,
    summary="Bulk resolve seat mappings with optional filters",
)
def list_seat_mappings(
    exam_id: int | None = Query(None, description="Filter by exam ID"),
    exam_hall_id: int | None = Query(None, description="Filter by exam hall ID"),
    unresolved_only: bool = Query(False, description="Return only unresolved mappings"),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR])),
):
    if unresolved_only:
        items = mapping_service.get_unresolved_mappings(db, exam_id=exam_id)
    else:
        items = mapping_service.resolve_bulk_seat_mappings(
            db, exam_id=exam_id, exam_hall_id=exam_hall_id
        )
    return SeatMappingListResponse(
        items=items,
        total=len(items),
        unresolved=sum(1 for i in items if i.status == "UNRESOLVED"),
    )
