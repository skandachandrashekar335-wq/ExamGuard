from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.identity_verification import (
    IdentityVerificationContextResponse,
    IdentityVerificationCreate,
    IdentityVerificationDetailedResponse,
    IdentityVerificationEvidenceCreate,
    IdentityVerificationEvidenceResponse,
    IdentityVerificationExamInfo,
    IdentityVerificationListResponse,
    IdentityVerificationResponse,
    IdentityVerificationStudentInfo,
    VerifyFaceResponse,
)
from app.services import identity_verification as iv_service
from app.services import identity_verification_decision as iv_decision

router = APIRouter(prefix="/identity-verifications", tags=["Identity Verifications"])


class CompleteRequest(BaseModel):
    decision: str = Field(..., description="Decision: MATCH, NO_MATCH, INCONCLUSIVE")
    failure_reason: str | None = Field(
        default=None, description="Failure reason (optional)"
    )


class FailRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Failure reason")


class CancelRequest(BaseModel):
    reason: str | None = Field(default=None, description="Cancellation reason")


class VerifyFaceRequest(BaseModel):
    """Request to run face verification on an attempt."""
    reference_image: str = Field(
        ..., min_length=1,
        description="Base64-encoded reference/enrollment image",
    )
    probe_image: str = Field(
        ..., min_length=1,
        description="Base64-encoded probe/capture image",
    )
    reference_image_format: str = Field(
        default="image/jpeg",
        description="MIME type of reference image",
    )
    probe_image_format: str = Field(
        default="image/jpeg",
        description="MIME type of probe image",
    )


@router.post(
    "",
    response_model=IdentityVerificationResponse,
    status_code=201,
    summary="Create an identity verification attempt",
)
def create_attempt(
    data: IdentityVerificationCreate,
    db: Session = Depends(get_db),
):
    try:
        return iv_service.create_attempt(db, data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get(
    "",
    response_model=IdentityVerificationListResponse,
    summary="List identity verification attempts with optional filters",
)
def list_attempts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    student_id: int | None = Query(None, description="Filter by student ID"),
    exam_registration_id: int | None = Query(
        None, description="Filter by exam registration ID"
    ),
    status: str | None = Query(None, description="Filter by status"),
    decision: str | None = Query(None, description="Filter by decision"),
    db: Session = Depends(get_db),
):
    result = iv_service.list_attempts(
        db,
        page=page,
        page_size=page_size,
        student_id=student_id,
        exam_registration_id=exam_registration_id,
        status=status,
        decision=decision,
    )
    return IdentityVerificationListResponse(
        items=[
            IdentityVerificationResponse.model_validate(a) for a in result["items"]
        ],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get(
    "/{attempt_id}",
    response_model=IdentityVerificationDetailedResponse,
    summary="Get an identity verification attempt with evidence",
)
def get_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
):
    attempt = iv_service.get_attempt(db, attempt_id)
    if not attempt:
        raise HTTPException(
            status_code=404, detail="Identity verification attempt not found"
        )
    evidence = (
        db.query(iv_service.IdentityVerificationEvidence)
        .filter(iv_service.IdentityVerificationEvidence.attempt_id == attempt_id)
        .order_by(iv_service.IdentityVerificationEvidence.id)
        .all()
    )
    return IdentityVerificationDetailedResponse(
        attempt=IdentityVerificationResponse.model_validate(attempt),
        evidence=[
            IdentityVerificationEvidenceResponse.model_validate(e) for e in evidence
        ],
    )


@router.get(
    "/{attempt_id}/context",
    response_model=IdentityVerificationContextResponse,
    summary="Get attempt with student, exam, and evidence context",
)
def get_attempt_context(
    attempt_id: int,
    db: Session = Depends(get_db),
):
    ctx = iv_service.get_attempt_with_context(db, attempt_id)
    if not ctx:
        raise HTTPException(
            status_code=404, detail="Identity verification attempt not found"
        )
    attempt = ctx["attempt"]
    evidence = ctx["evidence"]
    student = ctx["student"]
    exam = ctx["exam"]
    return IdentityVerificationContextResponse(
        attempt=IdentityVerificationResponse.model_validate(attempt),
        evidence=[
            IdentityVerificationEvidenceResponse.model_validate(e) for e in evidence
        ],
        student=IdentityVerificationStudentInfo.model_validate(student) if student else None,
        exam=IdentityVerificationExamInfo.model_validate(exam) if exam else None,
    )


@router.post(
    "/{attempt_id}/start",
    response_model=IdentityVerificationResponse,
    summary="Start an identity verification attempt",
)
def start_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
):
    try:
        return iv_service.start_attempt(db, attempt_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{attempt_id}/evidence",
    response_model=IdentityVerificationEvidenceResponse,
    status_code=201,
    summary="Record a piece of verification evidence",
)
def record_evidence(
    attempt_id: int,
    data: IdentityVerificationEvidenceCreate,
    db: Session = Depends(get_db),
):
    try:
        return iv_service.record_evidence(db, attempt_id, data)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{attempt_id}/verify-face",
    response_model=VerifyFaceResponse,
    status_code=201,
    summary="Run face verification provider and record evidence",
)
def verify_face(
    attempt_id: int,
    body: VerifyFaceRequest,
    db: Session = Depends(get_db),
):
    """Run face verification and persist evidence signals.

    The provider produces evidence. Authorization decisions are made
    separately via the evaluate endpoint.
    """
    import base64

    try:
        ref_bytes = base64.b64decode(body.reference_image)
        probe_bytes = base64.b64decode(body.probe_image)
    except Exception:
        raise HTTPException(
            status_code=422,
            detail="Invalid base64 encoding in reference_image or probe_image",
        )

    try:
        evidence_records = iv_service.verify_face(
            db,
            attempt_id,
            reference_image=ref_bytes,
            probe_image=probe_bytes,
            reference_image_format=body.reference_image_format,
            probe_image_format=body.probe_image_format,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return VerifyFaceResponse(
        attempt_id=attempt_id,
        evidence=[
            IdentityVerificationEvidenceResponse.model_validate(e)
            for e in evidence_records
        ],
    )


@router.post(
    "/{attempt_id}/complete",
    response_model=IdentityVerificationResponse,
    summary="Complete a verification attempt with a decision",
)
def complete_attempt(
    attempt_id: int,
    body: CompleteRequest,
    db: Session = Depends(get_db),
):
    try:
        return iv_service.complete_attempt(
            db, attempt_id, decision=body.decision,
            failure_reason=body.failure_reason,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{attempt_id}/evaluate",
    response_model=IdentityVerificationResponse,
    summary="Evaluate evidence and auto-produce a decision",
)
def evaluate_and_complete(
    attempt_id: int,
    db: Session = Depends(get_db),
):
    attempt = iv_service.get_attempt(db, attempt_id)
    if not attempt:
        raise HTTPException(
            status_code=404, detail="Identity verification attempt not found"
        )
    if attempt.status not in (
        iv_service.IdentityVerificationStatus.CREATED.value,
        iv_service.IdentityVerificationStatus.IN_PROGRESS.value,
    ):
        raise HTTPException(
            status_code=422,
            detail=f"Cannot evaluate attempt in status '{attempt.status}'",
        )
    evidence = (
        db.query(iv_service.IdentityVerificationEvidence)
        .filter(iv_service.IdentityVerificationEvidence.attempt_id == attempt_id)
        .all()
    )
    decision, reasoning = iv_decision.evaluate_evidence(evidence)
    try:
        return iv_service.complete_attempt(
            db, attempt_id, decision=decision, failure_reason=reasoning,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{attempt_id}/fail",
    response_model=IdentityVerificationResponse,
    summary="Mark a verification attempt as failed",
)
def fail_attempt(
    attempt_id: int,
    body: FailRequest,
    db: Session = Depends(get_db),
):
    try:
        return iv_service.fail_attempt(db, attempt_id, reason=body.reason)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{attempt_id}/cancel",
    response_model=IdentityVerificationResponse,
    summary="Cancel a verification attempt",
)
def cancel_attempt(
    attempt_id: int,
    body: CancelRequest = CancelRequest(),
    db: Session = Depends(get_db),
):
    try:
        return iv_service.cancel_attempt(db, attempt_id, reason=body.reason)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
