import json
import logging
from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.hall_ticket import HallTicket
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationDecision,
    IdentityVerificationEvidence,
    IdentityVerificationMethod,
    IdentityVerificationStatus,
    STATUS_TRANSITIONS,
)
from app.models.student import Student
from app.schemas.identity_verification import (
    IdentityVerificationCreate,
    IdentityVerificationEvidenceCreate,
)

logger = logging.getLogger(__name__)


def _validate_student_exists(db: Session, student_id: int) -> Student:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise LookupError(f"Student with id {student_id} not found")
    return student


def _validate_registration_exists(
    db: Session, exam_registration_id: int
) -> ExamRegistration:
    reg = db.query(ExamRegistration).filter(
        ExamRegistration.id == exam_registration_id
    ).first()
    if not reg:
        raise LookupError(
            f"Exam registration with id {exam_registration_id} not found"
        )
    return reg


def _validate_hall_ticket_exists(db: Session, hall_ticket_id: int) -> HallTicket:
    ht = db.query(HallTicket).filter(HallTicket.id == hall_ticket_id).first()
    if not ht:
        raise LookupError(f"Hall ticket with id {hall_ticket_id} not found")
    return ht


def _validate_status_transition(current: str, new: str) -> None:
    allowed = STATUS_TRANSITIONS.get(current, set())
    if new not in allowed:
        raise ValueError(
            f"Cannot transition from '{current}' to '{new}'. "
            f"Allowed: {sorted(allowed) if allowed else 'none (terminal)'}"
        )


def _validate_consistency(
    db: Session,
    student_id: int,
    exam_registration_id: int,
    hall_ticket_id: int | None,
) -> None:
    reg = _validate_registration_exists(db, exam_registration_id)
    if reg.student_id != student_id:
        raise ValueError(
            f"Registration {exam_registration_id} belongs to student "
            f"{reg.student_id}, not {student_id}"
        )
    if reg.status == RegistrationStatus.CANCELLED.value:
        raise ValueError(
            f"Registration {exam_registration_id} is cancelled"
        )
    if hall_ticket_id is not None:
        ht = _validate_hall_ticket_exists(db, hall_ticket_id)
        if ht.exam_registration_id != exam_registration_id:
            raise ValueError(
                f"Hall ticket {hall_ticket_id} belongs to registration "
                f"{ht.exam_registration_id}, not {exam_registration_id}"
            )


def _check_duplicate_active(
    db: Session,
    student_id: int,
    exam_registration_id: int,
) -> None:
    existing = (
        db.query(IdentityVerificationAttempt)
        .filter(
            IdentityVerificationAttempt.student_id == student_id,
            IdentityVerificationAttempt.exam_registration_id == exam_registration_id,
            IdentityVerificationAttempt.status.in_([
                IdentityVerificationStatus.CREATED.value,
                IdentityVerificationStatus.IN_PROGRESS.value,
            ]),
        )
        .first()
    )
    if existing:
        raise ValueError(
            f"Active identity verification attempt already exists "
            f"(id={existing.id}, status={existing.status})"
        )


def create_attempt(
    db: Session, data: IdentityVerificationCreate
) -> IdentityVerificationAttempt:
    _validate_student_exists(db, data.student_id)
    _validate_consistency(
        db, data.student_id, data.exam_registration_id, data.hall_ticket_id
    )
    _check_duplicate_active(db, data.student_id, data.exam_registration_id)

    valid_methods = {m.value for m in IdentityVerificationMethod}
    if data.verification_method not in valid_methods:
        raise ValueError(
            f"Invalid verification_method '{data.verification_method}'. "
            f"Must be one of: {sorted(valid_methods)}"
        )

    attempt = IdentityVerificationAttempt(
        student_id=data.student_id,
        exam_registration_id=data.exam_registration_id,
        hall_ticket_id=data.hall_ticket_id,
        status=IdentityVerificationStatus.CREATED.value,
        verification_method=data.verification_method,
        decision=IdentityVerificationDecision.PENDING.value,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def get_attempt(db: Session, attempt_id: int) -> IdentityVerificationAttempt | None:
    return (
        db.query(IdentityVerificationAttempt)
        .filter(IdentityVerificationAttempt.id == attempt_id)
        .first()
    )


def start_attempt(db: Session, attempt_id: int) -> IdentityVerificationAttempt:
    attempt = get_attempt(db, attempt_id)
    if not attempt:
        raise LookupError(f"Identity verification attempt {attempt_id} not found")
    _validate_status_transition(
        attempt.status, IdentityVerificationStatus.IN_PROGRESS.value
    )
    attempt.status = IdentityVerificationStatus.IN_PROGRESS.value
    attempt.started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(attempt)
    return attempt


def record_evidence(
    db: Session,
    attempt_id: int,
    data: IdentityVerificationEvidenceCreate,
) -> IdentityVerificationEvidence:
    attempt = get_attempt(db, attempt_id)
    if not attempt:
        raise LookupError(f"Identity verification attempt {attempt_id} not found")
    if attempt.status not in (
        IdentityVerificationStatus.CREATED.value,
        IdentityVerificationStatus.IN_PROGRESS.value,
    ):
        raise ValueError(
            f"Cannot record evidence on attempt in status '{attempt.status}'"
        )

    evidence = IdentityVerificationEvidence(
        attempt_id=attempt_id,
        signal_type=data.signal_type,
        signal_value=data.signal_value,
        provider_name=data.provider_name,
        provider_version=data.provider_version,
        confidence=data.confidence,
        details=data.details,
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence


def complete_attempt(
    db: Session,
    attempt_id: int,
    decision: str,
    failure_reason: str | None = None,
) -> IdentityVerificationAttempt:
    attempt = get_attempt(db, attempt_id)
    if not attempt:
        raise LookupError(f"Identity verification attempt {attempt_id} not found")
    _validate_status_transition(
        attempt.status, IdentityVerificationStatus.COMPLETED.value
    )

    valid_decisions = {d.value for d in IdentityVerificationDecision}
    if decision not in valid_decisions:
        raise ValueError(
            f"Invalid decision '{decision}'. Must be one of: {sorted(valid_decisions)}"
        )

    attempt.status = IdentityVerificationStatus.COMPLETED.value
    attempt.decision = decision
    if attempt.started_at is None:
        attempt.started_at = datetime.now(timezone.utc)
    attempt.completed_at = datetime.now(timezone.utc)
    if failure_reason:
        attempt.failure_reason = failure_reason
    db.commit()
    db.refresh(attempt)
    return attempt


def fail_attempt(
    db: Session,
    attempt_id: int,
    reason: str,
) -> IdentityVerificationAttempt:
    attempt = get_attempt(db, attempt_id)
    if not attempt:
        raise LookupError(f"Identity verification attempt {attempt_id} not found")
    _validate_status_transition(
        attempt.status, IdentityVerificationStatus.FAILED.value
    )
    attempt.status = IdentityVerificationStatus.FAILED.value
    attempt.failure_reason = reason
    if attempt.started_at is None:
        attempt.started_at = datetime.now(timezone.utc)
    attempt.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(attempt)
    return attempt


def cancel_attempt(
    db: Session,
    attempt_id: int,
    reason: str | None = None,
) -> IdentityVerificationAttempt:
    attempt = get_attempt(db, attempt_id)
    if not attempt:
        raise LookupError(f"Identity verification attempt {attempt_id} not found")
    _validate_status_transition(
        attempt.status, IdentityVerificationStatus.CANCELLED.value
    )
    attempt.status = IdentityVerificationStatus.CANCELLED.value
    if reason:
        attempt.failure_reason = reason
    if attempt.started_at is None:
        attempt.started_at = datetime.now(timezone.utc)
    attempt.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(attempt)
    return attempt


def list_attempts(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    student_id: int | None = None,
    exam_registration_id: int | None = None,
    status: str | None = None,
    decision: str | None = None,
) -> dict:
    query = db.query(IdentityVerificationAttempt)

    if student_id is not None:
        query = query.filter(IdentityVerificationAttempt.student_id == student_id)
    if exam_registration_id is not None:
        query = query.filter(
            IdentityVerificationAttempt.exam_registration_id == exam_registration_id
        )
    if status is not None:
        query = query.filter(IdentityVerificationAttempt.status == status)
    if decision is not None:
        query = query.filter(IdentityVerificationAttempt.decision == decision)

    total = query.count()
    items = (
        query.order_by(desc(IdentityVerificationAttempt.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_attempt_with_context(db: Session, attempt_id: int) -> dict | None:
    attempt = get_attempt(db, attempt_id)
    if not attempt:
        return None

    evidence = (
        db.query(IdentityVerificationEvidence)
        .filter(IdentityVerificationEvidence.attempt_id == attempt_id)
        .order_by(IdentityVerificationEvidence.id)
        .all()
    )

    student = db.query(Student).filter(Student.id == attempt.student_id).first()
    reg = db.query(ExamRegistration).filter(
        ExamRegistration.id == attempt.exam_registration_id
    ).first()
    exam = None
    hall_ticket = None
    if reg:
        from app.models.exam import Exam
        exam = db.query(Exam).filter(Exam.id == reg.exam_id).first()
    if attempt.hall_ticket_id:
        hall_ticket = db.query(HallTicket).filter(
            HallTicket.id == attempt.hall_ticket_id
        ).first()

    return {
        "attempt": attempt,
        "evidence": evidence,
        "student": student,
        "exam": exam,
        "hall_ticket": hall_ticket,
    }


def verify_face(
    db: Session,
    attempt_id: int,
    reference_image: bytes,
    probe_image: bytes,
    reference_image_format: str = "image/jpeg",
    probe_image_format: str = "image/jpeg",
) -> list[IdentityVerificationEvidence]:
    """Run face verification on an attempt and persist evidence.

    This function:
    1. Validates the attempt is eligible for face verification
    2. Obtains the configured face verification provider
    3. Calls provider.verify() to get evidence signals
    4. Converts provider result into IdentityVerificationEvidence records
    5. Persists evidence using the existing Phase 7 mechanism

    The provider produces evidence. This function does NOT make
    authorization decisions. The decision engine evaluates evidence
    separately via evaluate_evidence().

    Args:
        db: Database session.
        attempt_id: ID of the identity verification attempt.
        reference_image: Reference/enrollment image bytes.
        probe_image: Probe/capture image bytes.
        reference_image_format: MIME type of reference image.
        probe_image_format: MIME type of probe image.

    Returns:
        List of persisted IdentityVerificationEvidence records.

    Raises:
        LookupError: If attempt not found.
        ValueError: If attempt is not eligible for face verification.
    """
    from app.services.face_verification import (
        FaceVerificationRequest,
        ProviderUnavailableError,
        get_face_verification_provider,
    )

    # 1. Validate attempt eligibility
    attempt = get_attempt(db, attempt_id)
    if not attempt:
        raise LookupError(f"Identity verification attempt {attempt_id} not found")

    if attempt.status not in (
        IdentityVerificationStatus.CREATED.value,
        IdentityVerificationStatus.IN_PROGRESS.value,
    ):
        raise ValueError(
            f"Cannot verify face on attempt in status '{attempt.status}'. "
            f"Attempt must be CREATED or IN_PROGRESS."
        )

    if attempt.verification_method != IdentityVerificationMethod.FACE.value:
        raise ValueError(
            f"Attempt verification_method is '{attempt.verification_method}', "
            f"not 'FACE'. Face verification requires FACE method."
        )

    # 2. Validate input presence
    if not reference_image:
        raise ValueError("reference_image is required and must not be empty")
    if not probe_image:
        raise ValueError("probe_image is required and must not be empty")

    # 2b. Validate image integrity (defense-in-depth)
    from app.services.face_verification.validation import (
        ImageValidationError,
        validate_image_bytes,
    )
    try:
        validate_image_bytes(reference_image, field_name="reference_image")
    except ImageValidationError as e:
        raise ValueError(f"Invalid reference_image: {e.message}")
    try:
        validate_image_bytes(probe_image, field_name="probe_image")
    except ImageValidationError as e:
        raise ValueError(f"Invalid probe_image: {e.message}")

    # 3. Obtain provider
    provider = get_face_verification_provider()

    # 4. Check provider availability
    health = provider.health_check()
    if not health.available:
        fail_attempt(
            db, attempt_id,
            reason=f"Face verification provider unavailable: {health.message}",
        )
        raise ValueError(
            f"Face verification provider unavailable: {health.message}"
        )

    # 5. Build request and call provider
    request = FaceVerificationRequest(
        reference_image=reference_image,
        probe_image=probe_image,
        reference_image_format=reference_image_format,
        probe_image_format=probe_image_format,
        context={
            "attempt_id": attempt_id,
            "student_id": attempt.student_id,
        },
    )

    try:
        result = provider.verify(request)
    except ProviderUnavailableError as e:
        fail_attempt(db, attempt_id, reason=f"Provider error: {e.error.message}")
        raise ValueError(f"Provider error: {e.error.message}") from e

    # 6. Convert result → evidence records
    evidence_records = []

    # identity_match_score → similarity_score signal
    if result.identity_match_score is not None:
        data = IdentityVerificationEvidenceCreate(
            signal_type="similarity_score",
            signal_value=str(result.identity_match_score),
            provider_name=result.provider_name,
            provider_version=result.provider_version,
            confidence=result.identity_match_score,
            details=json.dumps({
                "source": "face_verification_provider",
                "signal": "identity_match_score",
            }),
        )
        evidence_records.append(record_evidence(db, attempt_id, data))

    # liveness_score → liveness_score signal
    if result.liveness_score is not None:
        data = IdentityVerificationEvidenceCreate(
            signal_type="liveness_score",
            signal_value=str(result.liveness_score),
            provider_name=result.provider_name,
            provider_version=result.provider_version,
            confidence=result.liveness_score,
            details=json.dumps({
                "source": "face_verification_provider",
                "signal": "liveness_score",
            }),
        )
        evidence_records.append(record_evidence(db, attempt_id, data))

    # liveness_passed → liveness signal (categorical: PASS/FAIL)
    if result.liveness_passed is not None:
        liveness_value = "PASS" if result.liveness_passed else "FAIL"
        data = IdentityVerificationEvidenceCreate(
            signal_type="liveness",
            signal_value=liveness_value,
            provider_name=result.provider_name,
            provider_version=result.provider_version,
            details=json.dumps({
                "source": "face_verification_provider",
                "signal": "liveness_passed",
            }),
        )
        evidence_records.append(record_evidence(db, attempt_id, data))

    # image_quality_score → image_quality signal (categorical: GOOD/POOR)
    if result.image_quality_score is not None:
        quality_value = "GOOD" if result.image_quality_score >= 0.5 else "POOR"
        data = IdentityVerificationEvidenceCreate(
            signal_type="image_quality",
            signal_value=quality_value,
            provider_name=result.provider_name,
            provider_version=result.provider_version,
            confidence=result.image_quality_score,
            details=json.dumps({
                "source": "face_verification_provider",
                "signal": "image_quality_score",
                "numeric_score": result.image_quality_score,
            }),
        )
        evidence_records.append(record_evidence(db, attempt_id, data))

    logger.info(
        "Face verification completed for attempt %d: "
        "%d evidence records created by provider %s",
        attempt_id, len(evidence_records), result.provider_name,
    )

    return evidence_records
