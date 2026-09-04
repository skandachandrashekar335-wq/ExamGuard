import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

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

    # 1b. Rate limiting
    from app.core.config import get_settings as _get_settings
    _settings = _get_settings()
    limiter = get_rate_limiter()

    if not limiter.check_global_limit(_settings.FACE_VERIFICATION_MAX_CALLS_PER_MINUTE):
        raise ValueError(
            "Face verification rate limit exceeded. "
            "Please try again later."
        )

    if not limiter.check_attempt_limit(
        attempt_id, _settings.FACE_VERIFICATION_MAX_CALLS_PER_ATTEMPT
    ):
        raise ValueError(
            f"Face verification call limit exceeded for this attempt "
            f"(max {_settings.FACE_VERIFICATION_MAX_CALLS_PER_ATTEMPT} calls)."
        )

    # 1c. Idempotency note: repeated verify_face calls on the same attempt
    # are ALLOWED — evidence accumulates. This is by design: the decision
    # engine processes ALL evidence. Blocking accumulation would break
    # existing retry/re-verification workflows. Status checks above prevent
    # calls on completed/failed/cancelled attempts.

    # Record this call for rate limiting
    limiter.record_attempt_call(attempt_id)
    limiter.record_global_call()

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
        from app.services.face_verification.audit import log_verification_event
        from app.services.face_verification.failure_categories import (
            categorize_provider_error,
        )
        category = categorize_provider_error(e.error.error_type.value)
        fail_attempt(
            db, attempt_id,
            reason=f"Provider error [{category.value}]: {e.error.message}",
        )
        log_verification_event(
            attempt_id=attempt_id,
            event_type="provider_error",
            category=category.value,
            detail=f"error_type={e.error.error_type.value}",
        )
        raise ValueError(f"Provider error: {e.error.message}") from e
    except Exception as e:
        from app.services.face_verification.audit import log_verification_event
        fail_attempt(
            db, attempt_id,
            reason=f"Unexpected provider error: {type(e).__name__}",
        )
        log_verification_event(
            attempt_id=attempt_id,
            event_type="provider_unexpected_error",
            category="PROVIDER_INTERNAL_ERROR",
            detail=f"error_type={type(e).__name__}",
        )
        raise ValueError("Face verification provider encountered an error") from e

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


# ---------------------------------------------------------------------------
# Rate Limiter (in-memory, bounded, per-process)
# ---------------------------------------------------------------------------


class _RateLimiter:
    """Simple in-memory rate limiter for face verification calls.

    Tracks per-attempt call counts and global per-minute call counts.
    Bounded: max 10,000 tracked attempt IDs, oldest evicted when full.
    Thread-safe via threading.Lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._attempt_calls: dict[int, int] = {}
        self._global_minute_calls: list[float] = []
        self._max_attempt_ids = 10_000

    def check_attempt_limit(
        self, attempt_id: int, max_calls: int
    ) -> bool:
        """Check if an attempt has exceeded its per-attempt call limit.

        Args:
            attempt_id: The verification attempt ID.
            max_calls: Maximum allowed calls per attempt (0 = unlimited).

        Returns:
            True if the call is allowed, False if rate limited.
        """
        if max_calls <= 0:
            return True
        with self._lock:
            count = self._attempt_calls.get(attempt_id, 0)
            return count < max_calls

    def record_attempt_call(self, attempt_id: int) -> None:
        """Record a face verification call for rate limiting.

        Args:
            attempt_id: The verification attempt ID.
        """
        with self._lock:
            self._attempt_calls[attempt_id] = (
                self._attempt_calls.get(attempt_id, 0) + 1
            )
            # Evict oldest entries if too many tracked
            if len(self._attempt_calls) > self._max_attempt_ids:
                # Remove half of entries (oldest by insertion order approximation)
                keys = list(self._attempt_calls.keys())
                for k in keys[: self._max_attempt_ids // 2]:
                    del self._attempt_calls[k]

    def check_global_limit(self, max_per_minute: int) -> bool:
        """Check if the global per-minute limit has been exceeded.

        Args:
            max_per_minute: Maximum calls per minute (0 = unlimited).

        Returns:
            True if the call is allowed, False if rate limited.
        """
        if max_per_minute <= 0:
            return True
        now = time.time()
        with self._lock:
            # Prune entries older than 60 seconds
            cutoff = now - 60.0
            self._global_minute_calls = [
                t for t in self._global_minute_calls if t > cutoff
            ]
            return len(self._global_minute_calls) < max_per_minute

    def record_global_call(self) -> None:
        """Record a global face verification call."""
        with self._lock:
            self._global_minute_calls.append(time.time())

    def reset(self) -> None:
        """Reset all rate limiter state. For testing only."""
        with self._lock:
            self._attempt_calls.clear()
            self._global_minute_calls.clear()


# Module-level singleton
_rate_limiter = _RateLimiter()


def get_rate_limiter() -> _RateLimiter:
    """Get the module-level rate limiter instance."""
    return _rate_limiter


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def _has_face_evidence(db: Session, attempt_id: int) -> bool:
    """Check if an attempt already has face verification evidence.

    Args:
        db: Database session.
        attempt_id: The verification attempt ID.

    Returns:
        True if similarity_score or liveness evidence already exists.
    """
    count = (
        db.query(IdentityVerificationEvidence)
        .filter(
            IdentityVerificationEvidence.attempt_id == attempt_id,
            IdentityVerificationEvidence.signal_type.in_([
                "similarity_score", "liveness",
            ]),
        )
        .count()
    )
    return count > 0


# ---------------------------------------------------------------------------
# Human Review & Override
# ---------------------------------------------------------------------------

# Valid decisions for override
_VALID_OVERRIDE_DECISIONS = {
    IdentityVerificationDecision.MATCH.value,
    IdentityVerificationDecision.NO_MATCH.value,
    IdentityVerificationDecision.INCONCLUSIVE.value,
}


def review_attempt(
    db: Session,
    attempt_id: int,
    *,
    reviewer_notes: str | None = None,
) -> IdentityVerificationAttempt:
    """Mark a completed/failed attempt as under human review.

    This is a lightweight review marker — it does NOT change the decision.
    The attempt must be in a terminal state (COMPLETED or FAILED) to be
    reviewed.

    Args:
        db: Database session.
        attempt_id: The verification attempt ID.
        reviewer_notes: Optional notes from the reviewer.

    Returns:
        Updated IdentityVerificationAttempt.

    Raises:
        LookupError: If attempt not found.
        ValueError: If attempt is not in a reviewable state.
    """
    from app.services.face_verification.audit import build_override_audit_entry

    attempt = get_attempt(db, attempt_id)
    if not attempt:
        raise LookupError(f"Identity verification attempt {attempt_id} not found")

    if attempt.status not in (
        IdentityVerificationStatus.COMPLETED.value,
        IdentityVerificationStatus.FAILED.value,
    ):
        raise ValueError(
            f"Cannot review attempt in status '{attempt.status}'. "
            f"Attempt must be COMPLETED or FAILED."
        )

    # Store review marker in failure_reason (does not change decision)
    review_entry = json.dumps({
        "audit_type": "review_requested",
        "reviewer_notes": reviewer_notes or "",
        "review_timestamp": datetime.now(timezone.utc).isoformat(),
        "original_decision": attempt.decision,
    }, ensure_ascii=False)

    attempt.failure_reason = review_entry
    db.commit()
    db.refresh(attempt)

    logger.info(
        "VERIFICATION_AUDIT: attempt=%d event=review_requested "
        "original_decision=%s",
        attempt_id, attempt.decision,
    )

    return attempt


def override_decision(
    db: Session,
    attempt_id: int,
    *,
    new_decision: str,
    reason: str,
    operator_id: str | None = None,
) -> IdentityVerificationAttempt:
    """Override the decision of a completed/failed verification attempt.

    This is an authorized human override. It:
    1. Validates the attempt is in a terminal state
    2. Validates the new decision is valid
    3. Records the override in the audit trail (failure_reason field)
    4. Updates the decision to the new value
    5. Does NOT erase original evidence

    The audit trail preserves:
    - Original automated decision
    - New human-decided decision
    - Reason for override
    - Timestamp
    - Operator ID (if provided)

    Args:
        db: Database session.
        attempt_id: The verification attempt ID.
        new_decision: The new decision (MATCH, NO_MATCH, INCONCLUSIVE).
        reason: Human-provided reason for the override.
        operator_id: Identifier of the operator performing the override.

    Returns:
        Updated IdentityVerificationAttempt.

    Raises:
        LookupError: If attempt not found.
        ValueError: If attempt is not in overrideable state or decision is invalid.
    """
    from app.services.face_verification.audit import build_override_audit_entry

    attempt = get_attempt(db, attempt_id)
    if not attempt:
        raise LookupError(f"Identity verification attempt {attempt_id} not found")

    if attempt.status not in (
        IdentityVerificationStatus.COMPLETED.value,
        IdentityVerificationStatus.FAILED.value,
    ):
        raise ValueError(
            f"Cannot override attempt in status '{attempt.status}'. "
            f"Attempt must be COMPLETED or FAILED."
        )

    if new_decision not in _VALID_OVERRIDE_DECISIONS:
        raise ValueError(
            f"Invalid override decision '{new_decision}'. "
            f"Must be one of: {sorted(_VALID_OVERRIDE_DECISIONS)}"
        )

    if not reason or not reason.strip():
        raise ValueError("Override reason is required and must not be empty")

    # Build audit entry preserving original decision
    original_decision = attempt.decision
    audit_entry = build_override_audit_entry(
        original_decision=original_decision,
        override_decision=new_decision,
        reason=reason.strip(),
        operator_id=operator_id,
        previous_status=attempt.status,
    )

    # Update attempt — decision changes, status stays terminal
    attempt.decision = new_decision
    attempt.failure_reason = audit_entry
    db.commit()
    db.refresh(attempt)

    logger.info(
        "VERIFICATION_AUDIT: attempt=%d event=override_applied "
        "original_decision=%s override_decision=%s operator=%s",
        attempt_id, original_decision, new_decision,
        operator_id or "unknown",
    )

    return attempt
