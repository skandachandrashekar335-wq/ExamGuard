from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.exam_registration import (
    ExamRegistrationCreate,
    ExamRegistrationListResponse,
    ExamRegistrationResponse,
    ExamRegistrationUpdate,
    ExamRegistrationWithDetails,
)
from app.services import exam_registration as reg_service

router = APIRouter(prefix="/exam-registrations", tags=["Exam Registrations"])


def _to_response(reg) -> ExamRegistrationWithDetails:
    resp = ExamRegistrationWithDetails.model_validate(reg)
    if reg.student:
        resp.student_usn = reg.student.usn
        resp.student_name = reg.student.name
    if reg.exam:
        resp.exam_name = reg.exam.exam_name
    return resp


@router.post(
    "",
    response_model=ExamRegistrationResponse,
    status_code=201,
    summary="Register a student for an exam",
)
def create_registration(data: ExamRegistrationCreate, db: Session = Depends(get_db)):
    try:
        return reg_service.create_registration(db, data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("", response_model=ExamRegistrationListResponse, summary="List registrations")
def list_registrations(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    student_id: int | None = Query(None, description="Filter by student ID"),
    exam_id: int | None = Query(None, description="Filter by exam ID"),
    status: str | None = Query(None, description="Filter by status (REGISTERED/CANCELLED)"),
    db: Session = Depends(get_db),
):
    registrations, total = reg_service.list_registrations(
        db,
        page=page,
        page_size=page_size,
        student_id=student_id,
        exam_id=exam_id,
        status=status,
    )
    return ExamRegistrationListResponse(
        items=[_to_response(r) for r in registrations],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/{registration_id}",
    response_model=ExamRegistrationWithDetails,
    summary="Get a registration",
)
def get_registration(registration_id: int, db: Session = Depends(get_db)):
    reg = reg_service.get_registration(db, registration_id)
    if not reg:
        raise HTTPException(status_code=404, detail="Registration not found")
    return _to_response(reg)


@router.patch(
    "/{registration_id}",
    response_model=ExamRegistrationResponse,
    summary="Update registration status",
)
def update_registration(
    registration_id: int,
    data: ExamRegistrationUpdate,
    db: Session = Depends(get_db),
):
    try:
        return reg_service.update_registration(db, registration_id, data.status)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete(
    "/{registration_id}",
    response_model=ExamRegistrationResponse,
    summary="Cancel a registration (status → CANCELLED)",
)
def cancel_registration(registration_id: int, db: Session = Depends(get_db)):
    try:
        return reg_service.cancel_registration(db, registration_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
