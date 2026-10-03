from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth import Role, require_role
from app.core.database import get_db
from app.models.document import Document, DocumentStatus, DocumentType
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.hall_ticket import HallTicket
from app.models.identity_verification import IdentityVerificationAttempt, IdentityVerificationMethod
from app.schemas.exam import (
    ExamCreate,
    ExamEnrollmentReadiness,
    ExamListResponse,
    ExamResponse,
    ExamResponseWithSubject,
    ExamUpdate,
)
from app.services import exam as exam_service

router = APIRouter(prefix="/exams", tags=["Exams"])


def _exam_to_response(exam) -> ExamResponseWithSubject:
    resp = ExamResponseWithSubject.model_validate(exam)
    if exam.subject:
        resp.subject_code = exam.subject.code
        resp.subject_name = exam.subject.name
    return resp


@router.post(
    "",
    response_model=ExamResponse,
    status_code=201,
    summary="Create a new exam",
)
def create_exam(data: ExamCreate, db: Session = Depends(get_db),
                _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR]))):
    try:
        return exam_service.create_exam(db, data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("", response_model=ExamListResponse, summary="List exams")
def list_exams(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search by exam name"),
    subject_id: int | None = Query(None, description="Filter by subject ID"),
    department: str | None = Query(None, description="Filter by department"),
    semester: int | None = Query(None, ge=1, le=8, description="Filter by semester"),
    exam_date: date | None = Query(None, description="Filter by exam date (YYYY-MM-DD)"),
    include_inactive: bool = Query(False, description="Include deactivated exams"),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    exams, total = exam_service.list_exams(
        db,
        page=page,
        page_size=page_size,
        search=search,
        subject_id=subject_id,
        department=department,
        semester=semester,
        exam_date=exam_date,
        include_inactive=include_inactive,
    )
    return ExamListResponse(
        items=[_exam_to_response(e) for e in exams],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{exam_id}", response_model=ExamResponseWithSubject, summary="Get an exam")
def get_exam(exam_id: int, db: Session = Depends(get_db),
             _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER]))):
    exam = exam_service.get_exam(db, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return _exam_to_response(exam)


@router.get(
    "/{exam_id}/enrollment-readiness",
    response_model=ExamEnrollmentReadiness,
    summary="Get candidate enrollment and reference-photo readiness for an exam",
)
def get_enrollment_readiness(
    exam_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
) -> ExamEnrollmentReadiness:
    exam = exam_service.get_exam(db, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found")

    candidates_enrolled = (
        db.query(func.count(ExamRegistration.id))
        .filter(
            ExamRegistration.exam_id == exam_id,
            ExamRegistration.status == RegistrationStatus.REGISTERED.value,
        )
        .scalar()
        or 0
    )
    reference_photos_enrolled = (
        db.query(func.count(func.distinct(IdentityVerificationAttempt.exam_registration_id)))
        .join(
            ExamRegistration,
            ExamRegistration.id == IdentityVerificationAttempt.exam_registration_id,
        )
        .filter(
            ExamRegistration.exam_id == exam_id,
            ExamRegistration.status == RegistrationStatus.REGISTERED.value,
            IdentityVerificationAttempt.verification_method
            == IdentityVerificationMethod.FACE.value,
            IdentityVerificationAttempt.reference_face_url.is_not(None),
        )
        .scalar()
        or 0
    )
    candidates_needing_review = (
        db.query(func.count(func.distinct(Document.id)))
        .outerjoin(HallTicket, HallTicket.document_id == Document.id)
        .filter(
            Document.exam_id == exam_id,
            Document.document_type == DocumentType.HALL_TICKET.value,
            or_(
                HallTicket.id.is_(None),
                Document.status == DocumentStatus.REVIEW_REQUIRED.value,
            ),
        )
        .scalar()
        or 0
    )
    return ExamEnrollmentReadiness(
        exam_id=exam_id,
        candidates_enrolled=candidates_enrolled,
        reference_photos_enrolled=reference_photos_enrolled,
        candidates_needing_review=candidates_needing_review,
    )


@router.patch("/{exam_id}", response_model=ExamResponse, summary="Update an exam")
def update_exam(exam_id: int, data: ExamUpdate, db: Session = Depends(get_db),
                _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR]))):
    try:
        return exam_service.update_exam(db, exam_id, data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete(
    "/{exam_id}",
    response_model=ExamResponse,
    summary="Deactivate an exam (soft delete)",
)
def deactivate_exam(exam_id: int, db: Session = Depends(get_db),
                    _user: dict = Depends(require_role([Role.ADMIN]))):
    try:
        return exam_service.deactivate_exam(db, exam_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
