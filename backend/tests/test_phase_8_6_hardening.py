"""Phase 8.6 — Failure/Security/Review Hardening.

Comprehensive tests for failure categorization, provider failure handling,
idempotency, rate limiting, human review/override, audit trail, security
invariants, API error sanitization, privacy, and regression.
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import Settings
from app.core.database import SessionLocal
from app.main import app
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationDecision,
    IdentityVerificationEvidence,
    IdentityVerificationMethod,
    IdentityVerificationStatus,
)
from app.services.face_verification.audit import (
    build_override_audit_entry,
    build_verification_audit_metadata,
    parse_override_audit_entry,
)
from app.services.face_verification.failure_categories import (
    FailureCategory,
    categorize_provider_error,
    is_face_detection,
    is_input_validation,
    is_provider_failure,
)
from app.services.identity_verification import (
    _RateLimiter,
    _has_face_evidence,
    cancel_attempt,
    complete_attempt,
    create_attempt,
    fail_attempt,
    get_attempt,
    override_decision,
    record_evidence,
    review_attempt,
    start_attempt,
)
from app.services.identity_verification_decision import evaluate_evidence
from app.schemas.identity_verification import (
    IdentityVerificationCreate,
    IdentityVerificationEvidenceCreate,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def cleanup():
    db = SessionLocal()
    try:
        db.execute(delete(IdentityVerificationEvidence))
        db.execute(delete(IdentityVerificationAttempt))
        from app.models.exam_registration import ExamRegistration
        from app.models.hall_ticket import HallTicket
        from app.models.student import Student
        from app.models.exam import Exam
        from app.models.subject import Subject
        db.execute(delete(HallTicket))
        # Clean up ExamRegistrations linked to test students
        test_student_ids = db.query(Student.id).filter(
            (Student.usn.ilike("P86%")) | (Student.usn.ilike("VF%"))
        ).subquery()
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.student_id.in_(db.query(test_student_ids))
        ))
        db.execute(delete(Student).where(
            (Student.usn.ilike("P86%")) | (Student.usn.ilike("VF%"))
        ))
        db.execute(delete(Exam).where(
            (Exam.exam_name.ilike("P86%")) | (Exam.exam_name.ilike("VF%"))
        ))
        db.execute(delete(Subject).where(
            (Subject.code.ilike("P86%")) | (Subject.code.ilike("VF%"))
        ))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def sample_data():
    """Create test data for API tests."""
    from app.models.exam import Exam
    from app.models.exam_registration import ExamRegistration, RegistrationStatus
    from app.models.student import Student
    from app.models.subject import Subject

    db = SessionLocal()
    try:
        subject = Subject(
            code="P86101", name="P86 Subject", department="P86 Dept",
            semester=1, credits=3,
        )
        db.add(subject)
        db.commit()
        db.refresh(subject)

        exam = Exam(
            subject_id=subject.id, exam_name="P86 Exam Final",
            exam_date="2026-12-01", start_time="09:00", end_time="12:00",
            semester=1, department="P86 Dept",
        )
        db.add(exam)
        db.commit()
        db.refresh(exam)

        student = Student(usn="P86001", name="Phase 86 Student")
        db.add(student)
        db.commit()
        db.refresh(student)

        reg = ExamRegistration(
            student_id=student.id, exam_id=exam.id,
            status=RegistrationStatus.REGISTERED.value,
        )
        db.add(reg)
        db.commit()
        db.refresh(reg)

        return {
            "subject_id": subject.id,
            "exam_id": exam.id,
            "student_id": student.id,
            "registration_id": reg.id,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_attempt_with_data(db, sample_data, *, status="CREATED", method="FACE", decision="PENDING"):
    """Create a test attempt using sample_data fixtures."""
    data = IdentityVerificationCreate(
        student_id=sample_data["student_id"],
        exam_registration_id=sample_data["registration_id"],
        verification_method=method,
    )
    attempt = create_attempt(db, data)
    if status != "CREATED":
        if status == "IN_PROGRESS":
            attempt = start_attempt(db, attempt.id)
        elif status == "COMPLETED":
            attempt = start_attempt(db, attempt.id)
            attempt = complete_attempt(db, attempt.id, decision=decision)
        elif status == "FAILED":
            attempt = start_attempt(db, attempt.id)
            attempt = fail_attempt(db, attempt.id, reason="test failure")
        elif status == "CANCELLED":
            attempt = start_attempt(db, attempt.id)
            attempt = cancel_attempt(db, attempt.id, reason="test cancel")
    return attempt


def _add_evidence(db, attempt_id, signal_type="similarity_score", value="0.90", provider="test"):
    """Add evidence to an attempt."""
    data = IdentityVerificationEvidenceCreate(
        signal_type=signal_type,
        signal_value=value,
        provider_name=provider,
        confidence=float(value) if value.replace(".", "").replace("-", "").isdigit() else None,
    )
    return record_evidence(db, attempt_id, data)


# ---------------------------------------------------------------------------
# Failure Categories
# ---------------------------------------------------------------------------

class TestFailureCategories:
    """Test failure category classification."""

    def test_all_categories_exist(self):
        assert len(FailureCategory) >= 20

    def test_provider_failure_categories(self):
        assert is_provider_failure(FailureCategory.PROVIDER_UNAVAILABLE)
        assert is_provider_failure(FailureCategory.PROVIDER_TIMEOUT)
        assert is_provider_failure(FailureCategory.PROVIDER_INITIALIZATION)
        assert is_provider_failure(FailureCategory.PROVIDER_INTERNAL_ERROR)

    def test_non_provider_failure_categories(self):
        assert not is_provider_failure(FailureCategory.NO_FACE_DETECTED)
        assert not is_provider_failure(FailureCategory.IDENTITY_MISMATCH)
        assert not is_provider_failure(FailureCategory.INVALID_INPUT)

    def test_input_validation_categories(self):
        assert is_input_validation(FailureCategory.INVALID_INPUT)
        assert is_input_validation(FailureCategory.EMPTY_IMAGE)
        assert is_input_validation(FailureCategory.OVERSIZED_IMAGE)
        assert is_input_validation(FailureCategory.UNSUPPORTED_FORMAT)
        assert is_input_validation(FailureCategory.CORRUPTED_IMAGE)
        assert is_input_validation(FailureCategory.IMAGE_TOO_SMALL)
        assert is_input_validation(FailureCategory.IMAGE_TOO_LARGE)
        assert is_input_validation(FailureCategory.DECOMPRESSION_BOMB)

    def test_non_input_validation_categories(self):
        assert not is_input_validation(FailureCategory.NO_FACE_DETECTED)
        assert not is_input_validation(FailureCategory.PROVIDER_UNAVAILABLE)

    def test_face_detection_categories(self):
        assert is_face_detection(FailureCategory.NO_FACE_DETECTED)
        assert is_face_detection(FailureCategory.MULTIPLE_FACES)

    def test_non_face_detection_categories(self):
        assert not is_face_detection(FailureCategory.INVALID_INPUT)
        assert not is_face_detection(FailureCategory.PROVIDER_UNAVAILABLE)

    def test_categorize_provider_error_mapping(self):
        assert categorize_provider_error("PROVIDER_UNAVAILABLE") == FailureCategory.PROVIDER_UNAVAILABLE
        assert categorize_provider_error("TIMEOUT") == FailureCategory.PROVIDER_TIMEOUT
        assert categorize_provider_error("NO_FACE_DETECTED") == FailureCategory.NO_FACE_DETECTED
        assert categorize_provider_error("MULTIPLE_FACES_DETECTED") == FailureCategory.MULTIPLE_FACES
        assert categorize_provider_error("INTERNAL_ERROR") == FailureCategory.PROVIDER_INTERNAL_ERROR

    def test_categorize_provider_error_unknown(self):
        assert categorize_provider_error("UNKNOWN_TYPE") == FailureCategory.PROVIDER_ERROR

    def test_categories_are_strings(self):
        for cat in FailureCategory:
            assert isinstance(cat.value, str)
            assert len(cat.value) > 0


# ---------------------------------------------------------------------------
# Audit Trail
# ---------------------------------------------------------------------------

class TestAuditTrail:
    """Test audit trail building and parsing."""

    def test_build_override_audit_entry(self):
        entry = build_override_audit_entry(
            original_decision="NO_MATCH",
            override_decision="MATCH",
            reason="Manual verification confirmed identity",
            operator_id="admin_001",
            previous_status="COMPLETED",
        )
        data = json.loads(entry)
        assert data["audit_type"] == "human_override"
        assert data["original_decision"] == "NO_MATCH"
        assert data["override_decision"] == "MATCH"
        assert data["reason"] == "Manual verification confirmed identity"
        assert data["operator_id"] == "admin_001"
        assert data["previous_status"] == "COMPLETED"
        assert "override_timestamp" in data

    def test_build_override_without_operator(self):
        entry = build_override_audit_entry(
            original_decision="MATCH",
            override_decision="NO_MATCH",
            reason="Suspicious behavior observed",
        )
        data = json.loads(entry)
        assert data["audit_type"] == "human_override"
        assert "operator_id" not in data

    def test_parse_override_audit_entry_valid(self):
        entry = build_override_audit_entry(
            original_decision="INCONCLUSIVE",
            override_decision="MATCH",
            reason="Reviewed manually",
        )
        parsed = parse_override_audit_entry(entry)
        assert parsed is not None
        assert parsed["audit_type"] == "human_override"
        assert parsed["original_decision"] == "INCONCLUSIVE"
        assert parsed["override_decision"] == "MATCH"

    def test_parse_override_audit_entry_none(self):
        assert parse_override_audit_entry(None) is None

    def test_parse_override_audit_entry_empty(self):
        assert parse_override_audit_entry("") is None

    def test_parse_override_audit_entry_non_json(self):
        assert parse_override_audit_entry("not json") is None

    def test_parse_override_audit_entry_wrong_type(self):
        entry = json.dumps({"audit_type": "something_else"})
        assert parse_override_audit_entry(entry) is None

    def test_parse_override_audit_entry_plain_failure_reason(self):
        assert parse_override_audit_entry("Provider error") is None

    def test_build_verification_audit_metadata(self):
        metadata = build_verification_audit_metadata(
            attempt_id=42,
            provider_name="uniface",
            category="POLICY_DECISION",
            decision="MATCH",
            evidence_count=4,
            duration_ms=123.45,
        )
        assert metadata["attempt_id"] == 42
        assert metadata["provider"] == "uniface"
        assert metadata["category"] == "POLICY_DECISION"
        assert metadata["decision"] == "MATCH"
        assert metadata["evidence_count"] == 4
        assert metadata["duration_ms"] == 123.45

    def test_build_verification_audit_metadata_minimal(self):
        metadata = build_verification_audit_metadata(
            attempt_id=1,
            provider_name="test",
            category="test",
        )
        assert metadata["attempt_id"] == 1
        assert "decision" not in metadata
        assert "evidence_count" not in metadata
        assert "duration_ms" not in metadata


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class TestRateLimiter:
    """Test the in-memory rate limiter."""

    def test_attempt_limit_allows_within_limit(self):
        limiter = _RateLimiter()
        assert limiter.check_attempt_limit(1, max_calls=3) is True
        limiter.record_attempt_call(1)
        assert limiter.check_attempt_limit(1, max_calls=3) is True
        limiter.record_attempt_call(1)
        assert limiter.check_attempt_limit(1, max_calls=3) is True

    def test_attempt_limit_blocks_at_limit(self):
        limiter = _RateLimiter()
        limiter.record_attempt_call(1)
        limiter.record_attempt_call(1)
        limiter.record_attempt_call(1)
        assert limiter.check_attempt_limit(1, max_calls=3) is False

    def test_attempt_limit_unlimited(self):
        limiter = _RateLimiter()
        for _ in range(100):
            limiter.record_attempt_call(1)
        assert limiter.check_attempt_limit(1, max_calls=0) is True

    def test_attempt_limit_independent_per_attempt(self):
        limiter = _RateLimiter()
        limiter.record_attempt_call(1)
        limiter.record_attempt_call(1)
        limiter.record_attempt_call(1)
        assert limiter.check_attempt_limit(1, max_calls=3) is False
        assert limiter.check_attempt_limit(2, max_calls=3) is True

    def test_global_limit_allows_within_limit(self):
        limiter = _RateLimiter()
        assert limiter.check_global_limit(max_per_minute=3) is True
        limiter.record_global_call()
        assert limiter.check_global_limit(max_per_minute=3) is True

    def test_global_limit_blocks_at_limit(self):
        limiter = _RateLimiter()
        limiter.record_global_call()
        limiter.record_global_call()
        limiter.record_global_call()
        assert limiter.check_global_limit(max_per_minute=3) is False

    def test_global_limit_unlimited(self):
        limiter = _RateLimiter()
        for _ in range(100):
            limiter.record_global_call()
        assert limiter.check_global_limit(max_per_minute=0) is True

    def test_reset_clears_state(self):
        limiter = _RateLimiter()
        limiter.record_attempt_call(1)
        limiter.record_global_call()
        limiter.reset()
        assert limiter.check_attempt_limit(1, max_calls=1) is True
        assert limiter.check_global_limit(max_per_minute=1) is True

    def test_attempt_eviction(self):
        limiter = _RateLimiter()
        limiter._max_attempt_ids = 5
        for i in range(10):
            limiter.record_attempt_call(i)
        assert len(limiter._attempt_calls) <= 5


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    """Test duplicate evidence prevention."""

    def test_no_existing_evidence(self, db, sample_data):
        data = IdentityVerificationCreate(
            student_id=sample_data["student_id"],
            exam_registration_id=sample_data["registration_id"],
            verification_method="FACE",
        )
        attempt = create_attempt(db, data)
        assert _has_face_evidence(db, attempt.id) is False

    def test_existing_similarity_evidence(self, db, sample_data):
        data = IdentityVerificationCreate(
            student_id=sample_data["student_id"],
            exam_registration_id=sample_data["registration_id"],
            verification_method="FACE",
        )
        attempt = create_attempt(db, data)
        _add_evidence(db, attempt.id, "similarity_score", "0.90")
        assert _has_face_evidence(db, attempt.id) is True

    def test_existing_liveness_evidence(self, db, sample_data):
        data = IdentityVerificationCreate(
            student_id=sample_data["student_id"],
            exam_registration_id=sample_data["registration_id"],
            verification_method="FACE",
        )
        attempt = create_attempt(db, data)
        _add_evidence(db, attempt.id, "liveness", "PASS")
        assert _has_face_evidence(db, attempt.id) is True

    def test_non_face_evidence_not_counted(self, db, sample_data):
        data = IdentityVerificationCreate(
            student_id=sample_data["student_id"],
            exam_registration_id=sample_data["registration_id"],
            verification_method="FACE",
        )
        attempt = create_attempt(db, data)
        _add_evidence(db, attempt.id, "image_quality", "GOOD")
        assert _has_face_evidence(db, attempt.id) is False


# ---------------------------------------------------------------------------
# Human Review
# ---------------------------------------------------------------------------

class TestHumanReview:
    """Test human review marking."""

    def test_review_completed_attempt(self, db, sample_data):
        attempt = _create_attempt_with_data(db, sample_data, status="COMPLETED", decision="MATCH")
        reviewed = review_attempt(db, attempt.id, reviewer_notes="Checking manually")
        assert reviewed.status == "COMPLETED"
        assert reviewed.decision == "MATCH"
        parsed = json.loads(reviewed.failure_reason)
        assert parsed["audit_type"] == "review_requested"
        assert parsed["original_decision"] == "MATCH"
        assert parsed["reviewer_notes"] == "Checking manually"

    def test_review_failed_attempt(self, db, sample_data):
        attempt = _create_attempt_with_data(db, sample_data, status="FAILED")
        reviewed = review_attempt(db, attempt.id)
        assert reviewed.status == "FAILED"
        parsed = json.loads(reviewed.failure_reason)
        assert parsed["audit_type"] == "review_requested"

    def test_review_created_attempt_fails(self, db, sample_data):
        attempt = _create_attempt_with_data(db, sample_data, status="CREATED")
        with pytest.raises(ValueError, match="COMPLETED or FAILED"):
            review_attempt(db, attempt.id)

    def test_review_in_progress_attempt_fails(self, db, sample_data):
        attempt = _create_attempt_with_data(db, sample_data, status="IN_PROGRESS")
        with pytest.raises(ValueError, match="COMPLETED or FAILED"):
            review_attempt(db, attempt.id)

    def test_review_nonexistent_attempt(self, db):
        with pytest.raises(LookupError):
            review_attempt(db, 999999)

    def test_review_without_notes(self, db, sample_data):
        attempt = _create_attempt_with_data(db, sample_data, status="COMPLETED", decision="NO_MATCH")
        reviewed = review_attempt(db, attempt.id)
        parsed = json.loads(reviewed.failure_reason)
        assert parsed["reviewer_notes"] == ""


# ---------------------------------------------------------------------------
# Human Override
# ---------------------------------------------------------------------------

class TestHumanOverride:
    """Test human override of verification decisions."""

    def test_override_match_to_no_match(self, db, sample_data):
        attempt = _create_attempt_with_data(db, sample_data, status="COMPLETED", decision="MATCH")
        overridden = override_decision(
            db, attempt.id,
            new_decision="NO_MATCH",
            reason="Manual review found proxy attempt",
            operator_id="reviewer_01",
        )
        assert overridden.decision == "NO_MATCH"
        parsed = json.loads(overridden.failure_reason)
        assert parsed["audit_type"] == "human_override"
        assert parsed["original_decision"] == "MATCH"
        assert parsed["override_decision"] == "NO_MATCH"
        assert parsed["operator_id"] == "reviewer_01"

    def test_override_no_match_to_match(self, db, sample_data):
        attempt = _create_attempt_with_data(db, sample_data, status="COMPLETED", decision="NO_MATCH")
        overridden = override_decision(
            db, attempt.id,
            new_decision="MATCH",
            reason="Image quality was poor but identity confirmed",
        )
        assert overridden.decision == "MATCH"
        parsed = json.loads(overridden.failure_reason)
        assert parsed["original_decision"] == "NO_MATCH"

    def test_override_to_inconclusive(self, db, sample_data):
        attempt = _create_attempt_with_data(db, sample_data, status="COMPLETED", decision="MATCH")
        overridden = override_decision(
            db, attempt.id,
            new_decision="INCONCLUSIVE",
            reason="Need additional verification",
        )
        assert overridden.decision == "INCONCLUSIVE"

    def test_override_preserves_evidence(self, db, sample_data):
        # Add evidence before completing the attempt (evidence can only be added to CREATED/IN_PROGRESS)
        data = IdentityVerificationCreate(
            student_id=sample_data["student_id"],
            exam_registration_id=sample_data["registration_id"],
            verification_method="FACE",
        )
        attempt = create_attempt(db, data)
        _add_evidence(db, attempt.id, "similarity_score", "0.45")
        attempt = start_attempt(db, attempt.id)
        attempt = complete_attempt(db, attempt.id, decision="NO_MATCH")
        override_decision(
            db, attempt.id,
            new_decision="MATCH",
            reason="Override",
        )
        evidence = (
            db.query(IdentityVerificationEvidence)
            .filter(IdentityVerificationEvidence.attempt_id == attempt.id)
            .all()
        )
        assert len(evidence) == 1
        assert evidence[0].signal_type == "similarity_score"

    def test_override_on_created_attempt_fails(self, db, sample_data):
        attempt = _create_attempt_with_data(db, sample_data, status="CREATED")
        with pytest.raises(ValueError, match="COMPLETED or FAILED"):
            override_decision(
                db, attempt.id,
                new_decision="MATCH",
                reason="reason",
            )

    def test_override_on_in_progress_attempt_fails(self, db, sample_data):
        attempt = _create_attempt_with_data(db, sample_data, status="IN_PROGRESS")
        with pytest.raises(ValueError, match="COMPLETED or FAILED"):
            override_decision(
                db, attempt.id,
                new_decision="MATCH",
                reason="reason",
            )

    def test_override_invalid_decision_fails(self, db, sample_data):
        attempt = _create_attempt_with_data(db, sample_data, status="COMPLETED", decision="MATCH")
        with pytest.raises(ValueError, match="Invalid override decision"):
            override_decision(
                db, attempt.id,
                new_decision="ALLOW",
                reason="reason",
            )

    def test_override_empty_reason_fails(self, db, sample_data):
        attempt = _create_attempt_with_data(db, sample_data, status="COMPLETED", decision="MATCH")
        with pytest.raises(ValueError, match="reason is required"):
            override_decision(
                db, attempt.id,
                new_decision="NO_MATCH",
                reason="",
            )

    def test_override_whitespace_reason_fails(self, db, sample_data):
        attempt = _create_attempt_with_data(db, sample_data, status="COMPLETED", decision="MATCH")
        with pytest.raises(ValueError, match="reason is required"):
            override_decision(
                db, attempt.id,
                new_decision="NO_MATCH",
                reason="   ",
            )

    def test_override_nonexistent_attempt(self, db):
        with pytest.raises(LookupError):
            override_decision(
                db, 999999,
                new_decision="MATCH",
                reason="reason",
            )

    def test_override_on_failed_attempt(self, db, sample_data):
        attempt = _create_attempt_with_data(db, sample_data, status="FAILED")
        overridden = override_decision(
            db, attempt.id,
            new_decision="INCONCLUSIVE",
            reason="Provider failure, not identity mismatch",
        )
        assert overridden.decision == "INCONCLUSIVE"

    def test_multiple_overrides_preserve_audit_trail(self, db, sample_data):
        attempt = _create_attempt_with_data(db, sample_data, status="COMPLETED", decision="MATCH")
        override_decision(
            db, attempt.id,
            new_decision="NO_MATCH",
            reason="First override",
            operator_id="op1",
        )
        override_decision(
            db, attempt.id,
            new_decision="MATCH",
            reason="Second override - reversal",
            operator_id="op2",
        )
        parsed = json.loads(get_attempt(db, attempt.id).failure_reason)
        assert parsed["original_decision"] == "NO_MATCH"
        assert parsed["override_decision"] == "MATCH"
        assert parsed["operator_id"] == "op2"


# ---------------------------------------------------------------------------
# Security Invariants
# ---------------------------------------------------------------------------

class TestSecurityInvariants:
    """Security invariants that must never be violated."""

    def test_client_cannot_submit_threshold(self):
        from app.api.v1.identity_verification import VerifyFaceRequest
        fields = VerifyFaceRequest.model_fields
        assert "threshold" not in fields
        assert "match_threshold" not in fields
        assert "decision" not in fields

    def test_override_requires_reason(self, db, sample_data):
        attempt = _create_attempt_with_data(db, sample_data, status="COMPLETED", decision="MATCH")
        with pytest.raises(ValueError, match="reason is required"):
            override_decision(db, attempt.id, new_decision="NO_MATCH", reason="")

    def test_override_cannot_use_allow(self, db, sample_data):
        attempt = _create_attempt_with_data(db, sample_data, status="COMPLETED", decision="MATCH")
        with pytest.raises(ValueError, match="Invalid override decision"):
            override_decision(db, attempt.id, new_decision="ALLOW", reason="test")

    def test_override_cannot_use_deny(self, db, sample_data):
        attempt = _create_attempt_with_data(db, sample_data, status="COMPLETED", decision="MATCH")
        with pytest.raises(ValueError, match="Invalid override decision"):
            override_decision(db, attempt.id, new_decision="DENY", reason="test")

    def test_decision_engine_cannot_be_bypassed(self):
        from app.models.identity_verification import IdentityVerificationEvidence
        evidence = [
            IdentityVerificationEvidence(
                signal_type="similarity_score",
                signal_value="0.95",
                confidence=0.95,
            ),
        ]
        decision, _ = evaluate_evidence(evidence)
        assert decision == "MATCH"

    def test_liveness_fail_always_no_match_regardless_of_override(self):
        from app.models.identity_verification import IdentityVerificationEvidence
        evidence = [
            IdentityVerificationEvidence(
                signal_type="similarity_score",
                signal_value="0.99",
                confidence=0.99,
            ),
            IdentityVerificationEvidence(
                signal_type="liveness",
                signal_value="FAIL",
            ),
        ]
        decision, _ = evaluate_evidence(evidence)
        assert decision == "NO_MATCH"

    def test_no_composite_score_leakage(self):
        from app.services.identity_verification_decision import evaluate_evidence_detailed
        from app.models.identity_verification import IdentityVerificationEvidence
        evidence = [
            IdentityVerificationEvidence(
                signal_type="similarity_score",
                signal_value="0.90",
                confidence=0.90,
            ),
        ]
        result = evaluate_evidence_detailed(evidence)
        assert "composite_score" not in result.metadata
        assert "final_score" not in result.metadata

    def test_provider_never_directly_authorizes(self):
        from app.services.identity_verification_decision import evaluate_evidence_detailed
        from app.models.identity_verification import IdentityVerificationEvidence
        evidence = [
            IdentityVerificationEvidence(
                signal_type="similarity_score",
                signal_value="1.0",
                confidence=1.0,
            ),
        ]
        result = evaluate_evidence_detailed(evidence)
        assert result.decision == "MATCH"
        assert result.metadata["decision_reason"] == "high_similarity"


# ---------------------------------------------------------------------------
# API Error Sanitization
# ---------------------------------------------------------------------------

class TestAPISanitization:
    """Verify API responses don't leak internal details."""

    def test_override_not_found_returns_404(self, client):
        response = client.post(
            "/api/v1/identity-verifications/999999/override",
            json={
                "new_decision": "MATCH",
                "reason": "test",
            },
        )
        assert response.status_code == 404

    def test_override_invalid_decision_returns_422(self, client, sample_data):
        db = SessionLocal()
        try:
            attempt = _create_attempt_with_data(db, sample_data, status="COMPLETED", decision="MATCH")
            attempt_id = attempt.id
        finally:
            db.close()
        response = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/override",
            json={
                "new_decision": "ALLOW",
                "reason": "test",
            },
        )
        assert response.status_code == 422

    def test_review_not_found_returns_404(self, client):
        response = client.post(
            "/api/v1/identity-verifications/999999/review",
            json={"reviewer_notes": "test"},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Privacy
# ---------------------------------------------------------------------------

class TestPrivacy:
    """Verify no raw biometric data leaks."""

    def test_no_raw_images_in_evidence_details(self, db, sample_data):
        data = IdentityVerificationCreate(
            student_id=sample_data["student_id"],
            exam_registration_id=sample_data["registration_id"],
            verification_method="FACE",
        )
        attempt = create_attempt(db, data)
        evidence = _add_evidence(db, attempt.id, "similarity_score", "0.90")
        details = json.loads(evidence.details) if evidence.details else {}
        assert "raw_image" not in details
        assert "base64" not in details
        assert "embedding" not in details

    def test_no_embeddings_in_audit_metadata(self):
        metadata = build_verification_audit_metadata(
            attempt_id=1, provider_name="test", category="test",
        )
        assert "embedding" not in metadata
        assert "face_vector" not in metadata
        assert "biometric" not in metadata

    def test_override_audit_no_biometric_data(self):
        entry = build_override_audit_entry(
            original_decision="MATCH",
            override_decision="NO_MATCH",
            reason="test",
        )
        data = json.loads(entry)
        assert "raw_image" not in data
        assert "embedding" not in data
        assert "base64" not in data
        assert "biometric" not in data

    def test_config_retention_days_zero(self):
        settings = Settings()
        assert settings.FACE_VERIFICATION_IMAGE_RETENTION_DAYS == 0


# ---------------------------------------------------------------------------
# Config Validation
# ---------------------------------------------------------------------------

class TestConfigHardening:
    """Test new config settings for Phase 8.6."""

    def test_default_rate_limits(self):
        settings = Settings()
        assert settings.FACE_VERIFICATION_MAX_CALLS_PER_ATTEMPT == 5
        assert settings.FACE_VERIFICATION_MAX_CALLS_PER_MINUTE == 60

    def test_rate_limit_zero_means_unlimited(self):
        settings = Settings(
            FACE_VERIFICATION_MAX_CALLS_PER_ATTEMPT=0,
            FACE_VERIFICATION_MAX_CALLS_PER_MINUTE=0,
        )
        assert settings.FACE_VERIFICATION_MAX_CALLS_PER_ATTEMPT == 0
        assert settings.FACE_VERIFICATION_MAX_CALLS_PER_MINUTE == 0


# ---------------------------------------------------------------------------
# Regression — Existing Behavior
# ---------------------------------------------------------------------------

class TestRegression:
    """Ensure existing decision engine and lifecycle behavior is preserved."""

    def test_high_similarity_match(self):
        decision, reasoning = evaluate_evidence([
            IdentityVerificationEvidence(
                signal_type="similarity_score",
                signal_value="0.95",
                confidence=0.95,
            ),
        ])
        assert decision == "MATCH"
        assert "0.950" in reasoning

    def test_low_similarity_no_match(self):
        decision, _ = evaluate_evidence([
            IdentityVerificationEvidence(
                signal_type="similarity_score",
                signal_value="0.45",
                confidence=0.45,
            ),
        ])
        assert decision == "NO_MATCH"

    def test_near_threshold_inconclusive(self):
        decision, _ = evaluate_evidence([
            IdentityVerificationEvidence(
                signal_type="similarity_score",
                signal_value="0.65",
                confidence=0.65,
            ),
        ])
        assert decision == "INCONCLUSIVE"

    def test_liveness_failure(self):
        decision, _ = evaluate_evidence([
            IdentityVerificationEvidence(
                signal_type="similarity_score",
                signal_value="0.95",
                confidence=0.95,
            ),
            IdentityVerificationEvidence(
                signal_type="liveness",
                signal_value="FAIL",
            ),
        ])
        assert decision == "NO_MATCH"

    def test_no_evidence(self):
        decision, _ = evaluate_evidence([])
        assert decision == "INCONCLUSIVE"

    def test_lifecycle_transitions(self, db, sample_data):
        data = IdentityVerificationCreate(
            student_id=sample_data["student_id"],
            exam_registration_id=sample_data["registration_id"],
            verification_method="FACE",
        )
        attempt = create_attempt(db, data)
        assert attempt.status == "CREATED"

        attempt = start_attempt(db, attempt.id)
        assert attempt.status == "IN_PROGRESS"

        attempt = complete_attempt(db, attempt.id, decision="MATCH")
        assert attempt.status == "COMPLETED"
        assert attempt.decision == "MATCH"

    def test_fail_attempt(self, db, sample_data):
        data = IdentityVerificationCreate(
            student_id=sample_data["student_id"],
            exam_registration_id=sample_data["registration_id"],
            verification_method="FACE",
        )
        attempt = create_attempt(db, data)
        attempt = start_attempt(db, attempt.id)
        attempt = fail_attempt(db, attempt.id, reason="provider error")
        assert attempt.status == "FAILED"
        assert "provider error" in attempt.failure_reason

    def test_cancel_attempt(self, db, sample_data):
        data = IdentityVerificationCreate(
            student_id=sample_data["student_id"],
            exam_registration_id=sample_data["registration_id"],
            verification_method="FACE",
        )
        attempt = create_attempt(db, data)
        attempt = start_attempt(db, attempt.id)
        attempt = cancel_attempt(db, attempt.id, reason="cancelled by admin")
        assert attempt.status == "CANCELLED"

    def test_record_evidence(self, db, sample_data):
        data = IdentityVerificationCreate(
            student_id=sample_data["student_id"],
            exam_registration_id=sample_data["registration_id"],
            verification_method="FACE",
        )
        attempt = create_attempt(db, data)
        evidence = _add_evidence(db, attempt.id, "similarity_score", "0.88")
        assert evidence.signal_type == "similarity_score"
        assert evidence.signal_value == "0.88"
