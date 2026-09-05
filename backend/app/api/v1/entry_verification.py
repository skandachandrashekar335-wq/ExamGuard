from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.entry_verification import (
    EntryVerificationCreate,
    EntryVerificationListResponse,
    EntryVerificationResponse,
    EscalateRequest,
    ResolveRequest,
)
from app.services import entry_verification as ev_service
from app.services.monitoring.publisher import (
    publish_entry_began,
    publish_entry_created,
    publish_entry_denied,
    publish_entry_escalated,
    publish_entry_granted,
    publish_entry_resolved,
)

router = APIRouter(prefix="/entry-verifications", tags=["Entry Verifications"])


class IdentityCheckRequest(BaseModel):
    identity_attempt_id: int | None = Field(
        default=None,
        description="ID of an existing identity verification attempt to link",
    )


@router.post(
    "",
    response_model=EntryVerificationResponse,
    status_code=201,
    summary="Create an entry verification",
)
def create_entry_verification(
    data: EntryVerificationCreate,
    db: Session = Depends(get_db),
):
    try:
        ev = ev_service.create_entry_verification(
            db,
            student_id=data.student_id,
            exam_registration_id=data.exam_registration_id,
            entry_point_id=data.entry_point_id,
            camera_id=data.camera_id,
            hall_ticket_id=data.hall_ticket_id,
        )
        publish_entry_created(
            entry_verification_id=ev.id,
            student_id=ev.student_id,
            exam_registration_id=ev.exam_registration_id,
            entry_point_id=ev.entry_point_id,
        )
        return ev
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get(
    "",
    response_model=EntryVerificationListResponse,
    summary="List entry verifications with optional filters",
)
def list_entry_verifications(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: str | None = Query(None, description="Filter by status"),
    entry_point_id: int | None = Query(None, description="Filter by entry point ID"),
    student_id: int | None = Query(None, description="Filter by student ID"),
    db: Session = Depends(get_db),
):
    result = ev_service.list_entry_verifications(
        db,
        page=page,
        page_size=page_size,
        student_id=student_id,
        entry_point_id=entry_point_id,
        status=status,
    )
    return EntryVerificationListResponse(
        items=[
            EntryVerificationResponse.model_validate(item) for item in result["items"]
        ],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get(
    "/{entry_verification_id}",
    response_model=EntryVerificationResponse,
    summary="Get an entry verification",
)
def get_entry_verification(
    entry_verification_id: int,
    db: Session = Depends(get_db),
):
    ev = ev_service.get_entry_verification(db, entry_verification_id)
    if not ev:
        raise HTTPException(
            status_code=404, detail="Entry verification not found"
        )
    return ev


@router.post(
    "/{entry_verification_id}/begin",
    response_model=EntryVerificationResponse,
    summary="Begin processing an entry verification",
)
def begin_processing(
    entry_verification_id: int,
    db: Session = Depends(get_db),
):
    try:
        ev = ev_service.begin_processing(db, entry_verification_id)
        publish_entry_began(entry_verification_id=ev.id)
        return ev
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{entry_verification_id}/hall-ticket-check",
    response_model=EntryVerificationResponse,
    summary="Run hall ticket validation",
)
def process_hall_ticket_check(
    entry_verification_id: int,
    db: Session = Depends(get_db),
):
    try:
        return ev_service.process_hall_ticket_check(db, entry_verification_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{entry_verification_id}/seat-check",
    response_model=EntryVerificationResponse,
    summary="Run seat assignment validation",
)
def process_seat_check(
    entry_verification_id: int,
    db: Session = Depends(get_db),
):
    try:
        return ev_service.process_seat_check(db, entry_verification_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{entry_verification_id}/identity-check",
    response_model=EntryVerificationResponse,
    summary="Run identity verification orchestration",
)
def process_identity_check(
    entry_verification_id: int,
    body: IdentityCheckRequest = IdentityCheckRequest(),
    db: Session = Depends(get_db),
):
    try:
        return ev_service.process_identity_check(
            db,
            entry_verification_id,
            identity_attempt_id=body.identity_attempt_id,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{entry_verification_id}/evaluate",
    response_model=EntryVerificationResponse,
    summary="Evaluate entry authorization",
)
def evaluate_entry(
    entry_verification_id: int,
    db: Session = Depends(get_db),
):
    try:
        ev = ev_service.evaluate_entry(db, entry_verification_id)
        # Publish the appropriate event based on the decision
        if ev.status == "GRANTED":
            publish_entry_granted(
                entry_verification_id=ev.id,
                student_id=ev.student_id,
                exam_id=None,
                hall_id=ev.exam_hall_id,
                entry_point_id=ev.entry_point_id,
            )
        elif ev.status == "DENIED":
            publish_entry_denied(
                entry_verification_id=ev.id,
                student_id=ev.student_id,
                exam_id=None,
                hall_id=ev.exam_hall_id,
                entry_point_id=ev.entry_point_id,
            )
        elif ev.status == "ESCALATED":
            publish_entry_escalated(
                entry_verification_id=ev.id,
                student_id=ev.student_id,
                reason=ev.escalation_reason,
                exam_id=None,
                hall_id=ev.exam_hall_id,
                entry_point_id=ev.entry_point_id,
            )
        return ev
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{entry_verification_id}/escalate",
    response_model=EntryVerificationResponse,
    summary="Escalate entry verification for human review",
)
def escalate_for_review(
    entry_verification_id: int,
    body: EscalateRequest,
    db: Session = Depends(get_db),
):
    try:
        ev = ev_service.escalate_for_review(
            db, entry_verification_id, reason=body.reason,
        )
        publish_entry_escalated(
            entry_verification_id=ev.id,
            student_id=ev.student_id,
            reason=ev.escalation_reason,
            exam_id=None,
            hall_id=ev.exam_hall_id,
            entry_point_id=ev.entry_point_id,
        )
        return ev
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{entry_verification_id}/resolve",
    response_model=EntryVerificationResponse,
    summary="Resolve an escalated entry verification",
)
def resolve_escalation(
    entry_verification_id: int,
    body: ResolveRequest,
    db: Session = Depends(get_db),
):
    try:
        ev = ev_service.resolve_escalation(
            db,
            entry_verification_id,
            granted=body.granted,
            reason=body.reason,
        )
        publish_entry_resolved(
            entry_verification_id=ev.id,
            student_id=ev.student_id,
            granted=body.granted,
            reason=body.reason,
            exam_id=None,
            hall_id=ev.exam_hall_id,
            entry_point_id=ev.entry_point_id,
        )
        return ev
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
