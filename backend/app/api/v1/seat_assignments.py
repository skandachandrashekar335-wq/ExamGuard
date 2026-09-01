from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.seat_assignment import (
    SeatAssignmentCreate,
    SeatAssignmentListResponse,
    SeatAssignmentResponse,
    SeatAssignmentUpdate,
    SeatAssignmentWithDetails,
)
from app.services import seat_assignment as seat_service

router = APIRouter(prefix="/seat-assignments", tags=["Seat Assignments"])


def _to_response(assignment) -> SeatAssignmentWithDetails:
    resp = SeatAssignmentWithDetails.model_validate(assignment)
    if assignment.student:
        resp.student_usn = assignment.student.usn
        resp.student_name = assignment.student.name
    if assignment.hall:
        resp.hall_building = assignment.hall.building
        resp.hall_room_number = assignment.hall.room_number
    return resp


@router.post(
    "",
    response_model=SeatAssignmentResponse,
    status_code=201,
    summary="Assign a seat to a registered student",
)
def create_assignment(data: SeatAssignmentCreate, db: Session = Depends(get_db)):
    try:
        return seat_service.create_assignment(db, data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("", response_model=SeatAssignmentListResponse, summary="List seat assignments")
def list_assignments(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    exam_id: int | None = Query(None, description="Filter by exam ID"),
    exam_hall_id: int | None = Query(None, description="Filter by hall ID"),
    student_id: int | None = Query(None, description="Filter by student ID"),
    registration_id: int | None = Query(None, description="Filter by registration ID"),
    status: str | None = Query(None, description="Filter by status (ASSIGNED/CANCELLED)"),
    db: Session = Depends(get_db),
):
    assignments, total = seat_service.list_assignments(
        db,
        page=page,
        page_size=page_size,
        exam_id=exam_id,
        exam_hall_id=exam_hall_id,
        student_id=student_id,
        registration_id=registration_id,
        status=status,
    )
    return SeatAssignmentListResponse(
        items=[_to_response(a) for a in assignments],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/{assignment_id}",
    response_model=SeatAssignmentWithDetails,
    summary="Get a seat assignment",
)
def get_assignment(assignment_id: int, db: Session = Depends(get_db)):
    assignment = seat_service.get_assignment(db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Seat assignment not found")
    return _to_response(assignment)


@router.patch(
    "/{assignment_id}",
    response_model=SeatAssignmentResponse,
    summary="Update assignment status",
)
def update_assignment(
    assignment_id: int,
    data: SeatAssignmentUpdate,
    db: Session = Depends(get_db),
):
    try:
        return seat_service.update_assignment(db, assignment_id, data.status)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete(
    "/{assignment_id}",
    response_model=SeatAssignmentResponse,
    summary="Cancel a seat assignment (status → CANCELLED)",
)
def cancel_assignment(assignment_id: int, db: Session = Depends(get_db)):
    try:
        return seat_service.cancel_assignment(db, assignment_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
