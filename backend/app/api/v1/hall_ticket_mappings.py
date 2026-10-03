from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import (
    Role,
    require_role,
    get_invigilator_scope,
    check_invigilator_scope,
    constrain_scope_filters,
)
from app.core.database import get_db
from app.models.exam_registration import ExamRegistration
from app.models.hall_ticket import HallTicket
from app.schemas.hall_ticket_seat_mapping import (
    SeatMappingListResponse,
    SeatMappingResponse,
)
from app.services import hall_ticket_seat_mapping as mapping_service

router = APIRouter(prefix="/hall-ticket-mappings", tags=["Hall Ticket Mappings"])


def _enforce_mapping_scope(
    db: Session, _user: dict, hall_ticket_id: int, exam_id: int | None, hall_id: int | None
) -> None:
    """Restrict seat-mapping reads to the caller's assigned exam/hall."""
    scope = get_invigilator_scope(_user, db)
    if scope is None:
        return
    if exam_id is None:
        ticket = (
            db.query(HallTicket).filter(HallTicket.id == hall_ticket_id).first()
        )
        registration = (
            db.query(ExamRegistration)
            .filter(ExamRegistration.id == ticket.exam_registration_id)
            .first()
            if ticket is not None and ticket.exam_registration_id is not None
            else None
        )
        exam_id = registration.exam_id if registration is not None else None
    if exam_id is None:
        raise HTTPException(
            status_code=403,
            detail="Access denied: hall ticket is outside your assigned exam",
        )
    check_invigilator_scope(scope, exam_id, hall_id)


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
    _enforce_mapping_scope(
        db, _user, hall_ticket_id, result.exam_id, result.exam_hall_id
    )
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
    exam_id, exam_hall_id = constrain_scope_filters(
        get_invigilator_scope(_user, db), exam_id, exam_hall_id
    )
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
