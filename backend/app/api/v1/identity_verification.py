from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.auth import Role, get_invigilator_scope, check_invigilator_scope, require_role
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


def _enforce_attempt_scope(db: Session, user: dict, attempt) -> None:
    """Enforce INVIGILATOR scope on an attempt. No-op for other roles."""
    if user.get("role") != Role.INVIGILATOR:
        return
    from app.models.exam_registration import ExamRegistration

    scope = get_invigilator_scope(user, db)
    exam_id = None
    if attempt.exam_registration_id:
        reg = db.query(ExamRegistration).filter(
            ExamRegistration.id == attempt.exam_registration_id
        ).first()
        if reg:
            exam_id = reg.exam_id
    check_invigilator_scope(scope, resource_exam_id=exam_id, resource_hall_id=None)


class CompleteRequest(BaseModel):
    decision: str = Field(..., description="Decision: MATCH, NO_MATCH, INCONCLUSIVE")
    failure_reason: str | None = Field(
        default=None, description="Failure reason (optional)"
    )


class FailRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Failure reason")


class CancelRequest(BaseModel):
    reason: str | None = Field(default=None, description="Cancellation reason")


class ReviewRequest(BaseModel):
    """Request to mark an attempt as under human review."""
    reviewer_notes: str | None = Field(
        default=None, description="Notes from the reviewer"
    )


class OverrideRequest(BaseModel):
    """Request to override a verification decision."""
    new_decision: str = Field(
        ..., description="New decision: MATCH, NO_MATCH, INCONCLUSIVE"
    )
    reason: str = Field(
        ..., min_length=1,
        description="Reason for the override (required)"
    )
    operator_id: str | None = Field(
        default=None,
        description="Identifier of the operator performing the override"
    )


class VerifyFaceRequest(BaseModel):
    """Request to run face verification on an attempt."""
    reference_image: str | None = Field(
        default=None,
        description="Base64-encoded reference/enrollment image. "
                    "If omitted, uses the stored reference_face_url from the attempt.",
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

    @model_validator(mode="after")
    def validate_base64_and_format(self) -> "VerifyFaceRequest":
        """Validate base64 encoding and format at the schema level."""
        import base64 as b64mod

        # Probe image is always required
        try:
            decoded = b64mod.b64decode(self.probe_image, validate=True)
        except Exception:
            raise ValueError("Invalid base64 encoding in probe_image")
        if len(decoded) == 0:
            raise ValueError("probe_image decodes to empty bytes")

        # Reference image is optional (uses stored reference if omitted)
        if self.reference_image is not None:
            try:
                decoded = b64mod.b64decode(self.reference_image, validate=True)
            except Exception:
                raise ValueError("Invalid base64 encoding in reference_image")
            if len(decoded) == 0:
                raise ValueError("reference_image decodes to empty bytes")

        format_fields = {
            "reference_image_format": self.reference_image_format,
            "probe_image_format": self.probe_image_format,
        }
        allowed = ("image/jpeg", "image/png")
        for fname, fmt in format_fields.items():
            if fmt not in allowed:
                raise ValueError(
                    f"Unsupported {fname}: '{fmt}'. "
                    f"Allowed: {', '.join(allowed)}"
                )

        return self


class SaveReferenceFaceRequest(BaseModel):
    """Request to save a reference face image for an attempt."""
    reference_image: str = Field(
        ..., min_length=1,
        description="Base64-encoded reference face image",
    )
    image_format: str = Field(
        default="image/jpeg",
        description="MIME type of the image",
    )


@router.post(
    "/{attempt_id}/reference-face",
    response_model=IdentityVerificationResponse,
    summary="Save a reference face image for later verification",
)
def save_reference_face(
    attempt_id: int,
    body: SaveReferenceFaceRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
):
    """Save a reference face image to Cloudinary and persist the URL on the attempt.

    This allows the invigilator page to later retrieve the stored reference
    without requiring the client to re-supply it on every verify call.
    """
    import base64

    from app.core.config import get_settings
    from app.services.face_verification.validation import (
        ImageValidationError,
        validate_image_bytes,
    )

    settings = get_settings()
    max_size_bytes = settings.FACE_VERIFICATION_MAX_IMAGE_SIZE_MB * 1024 * 1024

    try:
        ref_bytes = base64.b64decode(
            "".join(body.reference_image.split()), validate=True
        )
    except Exception:
        raise HTTPException(
            status_code=422,
            detail="Invalid base64 encoding in reference_image",
        )

    try:
        validate_image_bytes(
            ref_bytes,
            field_name="reference_image",
            max_size_bytes=max_size_bytes,
        )
    except ImageValidationError as e:
        raise HTTPException(status_code=422, detail=e.message)

    # Validate attempt exists and is eligible
    attempt = iv_service.get_attempt(db, attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    if attempt.status not in (
        iv_service.IdentityVerificationStatus.CREATED.value,
        iv_service.IdentityVerificationStatus.IN_PROGRESS.value,
    ):
        raise HTTPException(
            status_code=422,
            detail=f"Cannot save reference face for attempt in status '{attempt.status}'",
        )

    # Save to storage (Cloudinary or local fallback)
    from app.storage.cloudinary import CloudinaryStorage

    storage = CloudinaryStorage()
    ext = ".jpg" if body.image_format == "image/jpeg" else ".png"
    key = f"face-references/attempt-{attempt_id}{ext}"
    try:
        url = storage.save(key, ref_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to save reference face: {e}",
        )

    if not isinstance(url, str) or not url.lower().startswith(("http://", "https://")):
        raise HTTPException(
            status_code=502,
            detail="Image storage did not return a public URL",
        )

    # Persist URL on the attempt
    attempt.reference_face_url = url
    db.commit()
    db.refresh(attempt)

    return IdentityVerificationResponse.model_validate(attempt)


@router.get(
    "/{attempt_id}/reference-face",
    summary="Get the stored reference face URL for an attempt",
)
def get_reference_face(
    attempt_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR])),
):
    """Retrieve the stored reference face URL for an attempt.

    Returns 404 if no reference face has been saved yet.
    """
    attempt = iv_service.get_attempt(db, attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    _enforce_attempt_scope(db, _user, attempt)
    if not attempt.reference_face_url:
        raise HTTPException(
            status_code=404,
            detail="No reference face saved for this attempt",
        )
    if not str(attempt.reference_face_url).lower().startswith(
        ("http://", "https://")
    ):
        raise HTTPException(
            status_code=404,
            detail="Stored reference face is not a public URL; re-upload required",
        )
    return {
        "attempt_id": attempt_id,
        "reference_face_url": attempt.reference_face_url,
    }


@router.post(
    "",
    response_model=IdentityVerificationResponse,
    status_code=201,
    summary="Create an identity verification attempt",
)
def create_attempt(
    data: IdentityVerificationCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
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
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    # INVIGILATOR may only list attempts for their assigned exam
    if _user.get("role") == Role.INVIGILATOR:
        from app.models.exam_registration import ExamRegistration as _ER

        scope = get_invigilator_scope(_user, db)
        if scope is not None:
            allowed_reg_ids = [
                r.id for r in db.query(_ER).filter(_ER.exam_id == scope.exam_id).all()
            ]
            if exam_registration_id is not None:
                if exam_registration_id not in allowed_reg_ids:
                    raise HTTPException(
                        status_code=403,
                        detail="Access denied: resource outside your assigned exam",
                    )
            else:
                exam_registration_id = allowed_reg_ids[0] if allowed_reg_ids else -1

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
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    attempt = iv_service.get_attempt(db, attempt_id)
    if not attempt:
        raise HTTPException(
            status_code=404, detail="Identity verification attempt not found"
        )
    _enforce_attempt_scope(db, _user, attempt)
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
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR, Role.REVIEWER])),
):
    ctx = iv_service.get_attempt_with_context(db, attempt_id)
    if not ctx:
        raise HTTPException(
            status_code=404, detail="Identity verification attempt not found"
        )
    _enforce_attempt_scope(db, _user, ctx["attempt"])
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
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
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
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
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
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR])),
):
    """Run face verification and persist evidence signals.

    The provider produces evidence. Authorization decisions are made
    separately via the evaluate endpoint.

    INVIGILATOR may only verify attempts within their assigned exam scope.

    If reference_image is provided, it is used directly.
    If omitted, the stored reference_face_url on the attempt is fetched
    and downloaded for comparison.
    """
    import base64
    import urllib.request

    from app.core.config import get_settings
    from app.services.face_verification.validation import (
        ImageValidationError,
        validate_image_bytes,
    )

    settings = get_settings()
    max_size_bytes = settings.FACE_VERIFICATION_MAX_IMAGE_SIZE_MB * 1024 * 1024

    # Always load attempt first so INVIGILATOR scope can be enforced
    attempt = iv_service.get_attempt(db, attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    _enforce_attempt_scope(db, _user, attempt)

    # Resolve reference image bytes
    if body.reference_image is not None:
        try:
            ref_bytes = base64.b64decode(body.reference_image, validate=True)
        except Exception:
            raise HTTPException(
                status_code=422,
                detail="Invalid base64 encoding in reference_image",
            )
    else:
        # Fetch stored reference from attempt
        if not attempt.reference_face_url:
            raise HTTPException(
                status_code=422,
                detail="No reference_image provided and no stored reference face for this attempt. "
                       "Upload a reference face first via /reference-face endpoint.",
            )
        try:
            with urllib.request.urlopen(attempt.reference_face_url, timeout=30) as resp:
                ref_bytes = resp.read()
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to download stored reference face: {e}",
            )

    try:
        probe_bytes = base64.b64decode(body.probe_image, validate=True)
    except Exception:
        raise HTTPException(
            status_code=422,
            detail="Invalid base64 encoding in probe_image",
        )

    try:
        validate_image_bytes(
            ref_bytes,
            field_name="reference_image",
            max_size_bytes=max_size_bytes,
        )
    except ImageValidationError as e:
        raise HTTPException(status_code=422, detail=e.message)

    try:
        validate_image_bytes(
            probe_bytes,
            field_name="probe_image",
            max_size_bytes=max_size_bytes,
        )
    except ImageValidationError as e:
        raise HTTPException(status_code=422, detail=e.message)

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
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
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
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR, Role.INVIGILATOR])),
):
    attempt = iv_service.get_attempt(db, attempt_id)
    if not attempt:
        raise HTTPException(
            status_code=404, detail="Identity verification attempt not found"
        )
    _enforce_attempt_scope(db, _user, attempt)
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
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
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
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
):
    try:
        return iv_service.cancel_attempt(db, attempt_id, reason=body.reason)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{attempt_id}/review",
    response_model=IdentityVerificationResponse,
    summary="Mark a completed/failed attempt as under human review",
)
def review_attempt(
    attempt_id: int,
    body: ReviewRequest = ReviewRequest(),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
):
    """Mark a verification attempt as under human review.

    This is a lightweight review marker. It does NOT change the decision.
    The attempt must be in a terminal state (COMPLETED or FAILED).
    """
    try:
        return iv_service.review_attempt(
            db, attempt_id, reviewer_notes=body.reviewer_notes,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{attempt_id}/override",
    response_model=IdentityVerificationResponse,
    summary="Override a verification decision (authorized human override)",
)
def override_decision(
    attempt_id: int,
    body: OverrideRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role([Role.ADMIN, Role.OPERATOR])),
):
    """Override the decision of a completed/failed verification attempt.

    This is an authorized human override. It:
    - Validates the attempt is in a terminal state
    - Validates the new decision is valid
    - Records the override in the audit trail
    - Updates the decision to the new value
    - Does NOT erase original evidence

    The audit trail preserves:
    - Original automated decision
    - New human-decided decision
    - Reason for override
    - Timestamp
    - Operator ID (if provided)
    """
    try:
        return iv_service.override_decision(
            db,
            attempt_id,
            new_decision=body.new_decision,
            reason=body.reason,
            operator_id=body.operator_id,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
