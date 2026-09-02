from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.import_seat_assignments import (
    BulkCancelSeatRequest,
    BulkCancelSeatResponse,
    BulkSeatAssignmentRequest,
    BulkSeatAssignmentResponse,
)
from app.services import import_seat_assignments as import_service

router = APIRouter(prefix="/import", tags=["Import"])


@router.post(
    "/seat-assignments",
    response_model=BulkSeatAssignmentResponse,
    status_code=201,
    summary="Bulk assign seats in an exam hall",
)
def bulk_assign_seats(
    data: BulkSeatAssignmentRequest,
    db: Session = Depends(get_db),
):
    return import_service.bulk_assign_seats(db, data.exam_hall_id, data.assignments)


@router.post(
    "/seat-assignments/cancel",
    response_model=BulkCancelSeatResponse,
    status_code=200,
    summary="Bulk cancel seat assignments",
)
def bulk_cancel_seat_assignments(
    data: BulkCancelSeatRequest,
    db: Session = Depends(get_db),
):
    return import_service.bulk_cancel_assignments(db, data.assignment_ids)
