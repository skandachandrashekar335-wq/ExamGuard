from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.hall_ticket import (
    HallTicketCreate,
    HallTicketDetailedResponse,
    HallTicketDocumentInfo,
    HallTicketExamInfo,
    HallTicketListResponse,
    HallTicketResponse,
    HallTicketStudentInfo,
    HallTicketUpdate,
)
from app.services import hall_ticket as ht_service

router = APIRouter(prefix="/hall-tickets", tags=["Hall Tickets"])


class LinkDocumentRequest(BaseModel):
    document_id: int = Field(..., gt=0, description="Document ID to link")


class ApproveRejectRequest(BaseModel):
    verification_outcome_id: int | None = Field(
        default=None, gt=0, description="Verification outcome ID (optional)"
    )
    reason: str | None = Field(
        default=None, description="Rejection reason (required for reject)"
    )


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
    "/search",
    response_model=HallTicketListResponse,
    summary="Search hall tickets by USN, exam, subject, or status",
)
def search_hall_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    usn: str | None = Query(None, description="Search by student USN (partial match)"),
    exam_id: int | None = Query(None, description="Filter by exam ID"),
    status: str | None = Query(None, description="Filter by hall ticket status"),
    subject_code: str | None = Query(None, description="Filter by subject code"),
    db: Session = Depends(get_db),
):
    result = ht_service.search_hall_tickets(
        db,
        page=page,
        page_size=page_size,
        usn=usn,
        exam_id=exam_id,
        status=status,
        subject_code=subject_code,
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
    "/{hall_ticket_id}/detailed",
    response_model=HallTicketDetailedResponse,
    summary="Get hall ticket with linked student, exam, and document info",
)
def get_hall_ticket_detailed(
    hall_ticket_id: int,
    db: Session = Depends(get_db),
):
    ctx = ht_service.get_with_context(db, hall_ticket_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Hall ticket not found")
    ht = ctx["hall_ticket"]
    student = ctx.get("student")
    exam = ctx.get("exam")
    document = ctx.get("document")
    return HallTicketDetailedResponse(
        hall_ticket=HallTicketResponse.model_validate(ht),
        student=HallTicketStudentInfo.model_validate(student) if student else None,
        exam=HallTicketExamInfo.model_validate(exam) if exam else None,
        document=HallTicketDocumentInfo.model_validate(document) if document else None,
    )


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


@router.post(
    "/{hall_ticket_id}/link-document",
    response_model=HallTicketResponse,
    summary="Link a hall-ticket document to an existing hall ticket",
)
def link_document(
    hall_ticket_id: int,
    body: LinkDocumentRequest,
    db: Session = Depends(get_db),
):
    try:
        return ht_service.link_document(db, hall_ticket_id, body.document_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{hall_ticket_id}/approve",
    response_model=HallTicketResponse,
    summary="Approve a hall ticket (move to VERIFIED)",
)
def approve_hall_ticket(
    hall_ticket_id: int,
    body: ApproveRejectRequest = ApproveRejectRequest(),
    db: Session = Depends(get_db),
):
    try:
        return ht_service.approve(
            db, hall_ticket_id, verification_outcome_id=body.verification_outcome_id
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{hall_ticket_id}/reject",
    response_model=HallTicketResponse,
    summary="Reject a hall ticket (move to REJECTED)",
)
def reject_hall_ticket(
    hall_ticket_id: int,
    body: ApproveRejectRequest,
    db: Session = Depends(get_db),
):
    if not body.reason:
        raise HTTPException(status_code=422, detail="Rejection reason is required")
    try:
        return ht_service.reject(
            db,
            hall_ticket_id,
            reason=body.reason,
            verification_outcome_id=body.verification_outcome_id,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
