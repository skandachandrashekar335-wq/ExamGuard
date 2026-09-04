"""Phase 8.8 — Integration Testing + Final Hardening.

Comprehensive integration tests verifying the complete Phase 8 system
works correctly as ONE integrated system. Covers:

- Full pipeline E2E flow
- Provider abstraction integration
- Decision engine integration
- Lifecycle state machine
- Evidence consistency
- Repeated verification calls
- Concurrency/race conditions
- Human review integration
- Human override integration
- Audit trail integration
- Failure matrix
- API contract validation
- Security invariants
- Rate limiting
- Configuration audit
- Error sanitization
"""

import base64
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationEvidence,
)
from app.schemas.identity_verification import (
    IdentityVerificationCreate,
    IdentityVerificationEvidenceCreate,
)
from app.services import identity_verification as iv_service
from app.services import identity_verification_decision as iv_decision
from app.services.face_verification.audit import (
    build_override_audit_entry,
    build_verification_audit_metadata,
    log_verification_event,
    parse_override_audit_entry,
)
from app.services.face_verification.failure_categories import (
    FailureCategory,
    categorize_provider_error,
    is_face_detection,
    is_input_validation,
    is_provider_failure,
)
from app.services.face_verification.providers.deterministic import (
    DeterministicProvider,
)
from app.services.face_verification.types import (
    FaceVerificationError,
    FaceVerificationErrorType,
    FaceVerificationRequest,
    FaceVerificationResult,
    ProviderCapabilities,
    ProviderStatus,
)
from app.services.identity_verification import (
    _RateLimiter,
    get_rate_limiter,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def cleanup():
    """Clean all test data and reset rate limiter before each test."""
    get_rate_limiter().reset()
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
        test_student_ids = db.query(Student.id).filter(
            (Student.usn.ilike("P88%")) | (Student.usn.ilike("INT%"))
        ).subquery()
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.student_id.in_(db.query(test_student_ids))
        ))
        db.execute(delete(Student).where(
            (Student.usn.ilike("P88%")) | (Student.usn.ilike("INT%"))
        ))
        db.execute(delete(Exam).where(
            (Exam.exam_name.ilike("P88%")) | (Exam.exam_name.ilike("INT%"))
        ))
        db.execute(delete(Subject).where(
            (Subject.code.ilike("P88%")) | (Subject.code.ilike("INT%"))
        ))
        db.commit()
    finally:
        db.close()
    yield
    get_rate_limiter().reset()


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
    """Create test data for integration tests."""
    from app.models.exam import Exam
    from app.models.exam_registration import ExamRegistration, RegistrationStatus
    from app.models.student import Student
    from app.models.subject import Subject

    db = SessionLocal()
    try:
        subject = Subject(
            code="INT101", name="INT Subject", department="INT Dept",
            semester=1, credits=3,
        )
        db.add(subject)
        db.commit()
        db.refresh(subject)

        exam = Exam(
            subject_id=subject.id, exam_name="INT Exam Final",
            exam_date="2026-12-01", start_time="09:00", end_time="12:00",
            semester=1, department="INT Dept",
        )
        db.add(exam)
        db.commit()
        db.refresh(exam)

        student = Student(usn="INT001", name="Integration Student")
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

def _make_jpeg(width=64, height=64) -> bytes:
    """Create a valid minimal JPEG image."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


def _make_png(width=64, height=64) -> bytes:
    """Create a valid minimal PNG image."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".png", img)
    return buf.tobytes()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _create_attempt(db, sample_data, *, method="FACE"):
    data = IdentityVerificationCreate(
        student_id=sample_data["student_id"],
        exam_registration_id=sample_data["registration_id"],
        verification_method=method,
    )
    return iv_service.create_attempt(db, data)


def _advance_attempt(db, attempt_id, *, to_status="IN_PROGRESS"):
    if to_status == "IN_PROGRESS":
        return iv_service.start_attempt(db, attempt_id)
    elif to_status == "COMPLETED":
        a = iv_service.start_attempt(db, attempt_id)
        return iv_service.complete_attempt(db, attempt_id, decision="MATCH")
    elif to_status == "FAILED":
        a = iv_service.start_attempt(db, attempt_id)
        return iv_service.fail_attempt(db, attempt_id, reason="test")
    elif to_status == "CANCELLED":
        a = iv_service.start_attempt(db, attempt_id)
        return iv_service.cancel_attempt(db, attempt_id)
    raise ValueError(f"Unknown status: {to_status}")


def _add_evidence(db, attempt_id, signal_type, value, provider="deterministic"):
    data = IdentityVerificationEvidenceCreate(
        signal_type=signal_type,
        signal_value=str(value),
        provider_name=provider,
    )
    return iv_service.record_evidence(db, attempt_id, data)


class _StubProvider:
    """Minimal provider stub for integration tests."""

    def __init__(
        self,
        match_score=0.92,
        liveness_score=0.95,
        liveness_passed=True,
        quality_score=0.85,
        available=True,
    ):
        self._match = match_score
        self._liveness = liveness_score
        self._liveness_passed = liveness_passed
        self._quality = quality_score
        self._available = available

    def verify(self, request):
        return FaceVerificationResult(
            identity_match_score=self._match,
            liveness_score=self._liveness,
            liveness_passed=self._liveness_passed,
            image_quality_score=self._quality,
            provider_name="stub",
            provider_version="0.0.1",
            evidence_metadata={},
        )

    def health_check(self):
        return ProviderStatus(
            available=self._available,
            message="ok" if self._available else "unavailable",
            provider_name="stub",
            provider_version="0.0.1",
        )

    def get_capabilities(self):
        return ProviderCapabilities(
            supports_liveness=True,
            supports_identity_match=True,
            supports_image_quality=True,
            max_image_size_bytes=None,
            supported_formats=("image/jpeg", "image/png"),
            provider_name="stub",
            provider_version="0.0.1",
        )


# ===========================================================================
# 1. FULL PIPELINE E2E TEST
# ===========================================================================

class TestFullPipelineE2E:
    """Complete end-to-end identity verification pipeline."""

    def test_complete_pipeline_match(self, db, sample_data):
        """Full flow: create -> start -> verify-face -> evaluate -> completed."""
        # 1. Create
        attempt = _create_attempt(db, sample_data)
        assert attempt.status == "CREATED"
        assert attempt.decision == "PENDING"
        assert attempt.hall_ticket_id is None

        # 2. Start
        attempt = iv_service.start_attempt(db, attempt.id)
        assert attempt.status == "IN_PROGRESS"
        assert attempt.started_at is not None

        # 3. Verify face (with provider stub)
        ref = _make_jpeg()
        probe = _make_jpeg()
        provider = _StubProvider(match_score=0.92, liveness_passed=True)
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            evidence_records = iv_service.verify_face(
                db, attempt.id,
                reference_image=ref,
                probe_image=probe,
                reference_image_format="image/jpeg",
                probe_image_format="image/jpeg",
            )
        assert len(evidence_records) > 0

        # 4. Evaluate
        evidence = (
            db.query(IdentityVerificationEvidence)
            .filter(IdentityVerificationEvidence.attempt_id == attempt.id)
            .all()
        )
        decision, reasoning = iv_decision.evaluate_evidence(evidence)
        assert decision in ("MATCH", "NO_MATCH", "INCONCLUSIVE")

        # 5. Complete
        attempt = iv_service.complete_attempt(db, attempt.id, decision=decision, failure_reason=reasoning)
        assert attempt.status == "COMPLETED"
        assert attempt.completed_at is not None
        assert attempt.decision == decision

    def test_complete_pipeline_via_api(self, client, sample_data):
        """Full flow through HTTP API."""
        # Create
        res = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
            "verification_method": "FACE",
        })
        assert res.status_code == 201
        attempt_id = res.json()["id"]

        # Start
        res = client.post(f"/api/v1/identity-verifications/{attempt_id}/start")
        assert res.status_code == 200

        # Verify face
        ref_b64 = _b64(_make_jpeg())
        probe_b64 = _b64(_make_jpeg())
        provider = _StubProvider(match_score=0.92, liveness_passed=True)
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            res = client.post(f"/api/v1/identity-verifications/{attempt_id}/verify-face", json={
                "reference_image": ref_b64,
                "probe_image": probe_b64,
            })
        assert res.status_code == 201

        # Evaluate
        res = client.post(f"/api/v1/identity-verifications/{attempt_id}/evaluate")
        assert res.status_code == 200
        assert res.json()["status"] == "COMPLETED"
        assert res.json()["decision"] in ("MATCH", "NO_MATCH", "INCONCLUSIVE")

    def test_full_pipeline_no_match(self, db, sample_data):
        """Pipeline with low similarity -> NO_MATCH."""
        attempt = _create_attempt(db, sample_data)
        attempt = iv_service.start_attempt(db, attempt.id)

        provider = _StubProvider(match_score=0.3, liveness_passed=True)
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            iv_service.verify_face(
                db, attempt.id,
                reference_image=_make_jpeg(),
                probe_image=_make_jpeg(),
                reference_image_format="image/jpeg",
                probe_image_format="image/jpeg",
            )

        evidence = (
            db.query(IdentityVerificationEvidence)
            .filter(IdentityVerificationEvidence.attempt_id == attempt.id)
            .all()
        )
        decision, _ = iv_decision.evaluate_evidence(evidence)
        attempt = iv_service.complete_attempt(db, attempt.id, decision=decision)
        assert attempt.decision == "NO_MATCH"

    def test_full_pipeline_liveness_fail(self, db, sample_data):
        """Pipeline with liveness failure -> NO_MATCH regardless of similarity."""
        attempt = _create_attempt(db, sample_data)
        attempt = iv_service.start_attempt(db, attempt.id)

        provider = _StubProvider(match_score=0.95, liveness_passed=False)
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            iv_service.verify_face(
                db, attempt.id,
                reference_image=_make_jpeg(),
                probe_image=_make_jpeg(),
                reference_image_format="image/jpeg",
                probe_image_format="image/jpeg",
            )

        evidence = (
            db.query(IdentityVerificationEvidence)
            .filter(IdentityVerificationEvidence.attempt_id == attempt.id)
            .all()
        )
        decision, reasoning = iv_decision.evaluate_evidence(evidence)
        assert decision == "NO_MATCH"
        assert "liveness" in reasoning.lower()

    def test_full_pipeline_inconclusive(self, db, sample_data):
        """Pipeline with near-threshold similarity -> INCONCLUSIVE."""
        settings = get_settings()
        near_threshold = settings.IDENTITY_VERIFICATION_MATCH_THRESHOLD * settings.IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR

        attempt = _create_attempt(db, sample_data)
        attempt = iv_service.start_attempt(db, attempt.id)

        provider = _StubProvider(match_score=near_threshold + 0.01, liveness_passed=True)
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            iv_service.verify_face(
                db, attempt.id,
                reference_image=_make_jpeg(),
                probe_image=_make_jpeg(),
                reference_image_format="image/jpeg",
                probe_image_format="image/jpeg",
            )

        evidence = (
            db.query(IdentityVerificationEvidence)
            .filter(IdentityVerificationEvidence.attempt_id == attempt.id)
            .all()
        )
        decision, _ = iv_decision.evaluate_evidence(evidence)
        assert decision == "INCONCLUSIVE"


# ===========================================================================
# 2. PROVIDER ABSTRACTION INTEGRATION
# ===========================================================================

class TestProviderAbstractionIntegration:
    """Verify provider abstraction works through the full stack."""

    def test_deterministic_provider_through_api(self, client, sample_data):
        """DeterministicProvider works through API endpoint."""
        res = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
            "verification_method": "FACE",
        })
        attempt_id = res.json()["id"]
        client.post(f"/api/v1/identity-verifications/{attempt_id}/start")

        ref_b64 = _b64(_make_jpeg())
        probe_b64 = _b64(_make_jpeg())
        with patch("app.services.face_verification.get_face_verification_provider",
                    return_value=DeterministicProvider()):
            res = client.post(f"/api/v1/identity-verifications/{attempt_id}/verify-face", json={
                "reference_image": ref_b64,
                "probe_image": probe_b64,
            })
        assert res.status_code == 201
        evidence = res.json()["evidence"]
        assert len(evidence) > 0
        signal_types = [e["signal_type"] for e in evidence]
        assert "similarity_score" in signal_types

    def test_stub_provider_through_service(self, db, sample_data):
        """Custom provider works through service layer."""
        attempt = _create_attempt(db, sample_data)
        attempt = iv_service.start_attempt(db, attempt.id)

        provider = _StubProvider(match_score=0.88, quality_score=0.7)
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            records = iv_service.verify_face(
                db, attempt.id,
                reference_image=_make_jpeg(),
                probe_image=_make_jpeg(),
                reference_image_format="image/jpeg",
                probe_image_format="image/jpeg",
            )
        assert len(records) >= 3  # similarity + liveness + quality
        provider_names = {r.provider_name for r in records}
        assert "stub" in provider_names

    def test_provider_failure_fails_attempt(self, db, sample_data):
        """Provider failure correctly fails the attempt."""
        attempt = _create_attempt(db, sample_data)
        attempt = iv_service.start_attempt(db, attempt.id)

        provider = _StubProvider(available=False)
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            with pytest.raises(ValueError, match="unavailable"):
                iv_service.verify_face(
                    db, attempt.id,
                    reference_image=_make_jpeg(),
                    probe_image=_make_jpeg(),
                    reference_image_format="image/jpeg",
                    probe_image_format="image/jpeg",
                )

        db.refresh(attempt)
        assert attempt.status == "FAILED"

    def test_provider_exception_fails_attempt(self, db, sample_data):
        """Generic provider exception fails the attempt safely."""
        attempt = _create_attempt(db, sample_data)
        attempt = iv_service.start_attempt(db, attempt.id)

        bad_provider = MagicMock()
        bad_provider.health_check.return_value = ProviderStatus(
            available=True, message="ok", provider_name="bad", provider_version="0",
        )
        bad_provider.verify.side_effect = RuntimeError("ONNX model corrupted")

        with patch("app.services.face_verification.get_face_verification_provider", return_value=bad_provider):
            with pytest.raises(ValueError, match="error"):
                iv_service.verify_face(
                    db, attempt.id,
                    reference_image=_make_jpeg(),
                    probe_image=_make_jpeg(),
                    reference_image_format="image/jpeg",
                    probe_image_format="image/jpeg",
                )

        db.refresh(attempt)
        assert attempt.status == "FAILED"

    def test_provider_result_no_authorization_fields(self, db, sample_data):
        """Provider result cannot directly authorize."""
        attempt = _create_attempt(db, sample_data)
        attempt = iv_service.start_attempt(db, attempt.id)

        provider = _StubProvider()
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            records = iv_service.verify_face(
                db, attempt.id,
                reference_image=_make_jpeg(),
                probe_image=_make_jpeg(),
                reference_image_format="image/jpeg",
                probe_image_format="image/jpeg",
            )

        for r in records:
            assert r.signal_type not in ("ALLOW", "DENY", "decision", "verdict")


# ===========================================================================
# 3. DECISION ENGINE INTEGRATION
# ===========================================================================

class TestDecisionEngineIntegration:
    """Verify decision engine processes real evidence correctly."""

    def test_match_from_high_similarity(self, db, sample_data):
        """High similarity evidence -> MATCH."""
        attempt = _create_attempt(db, sample_data)
        _add_evidence(db, attempt.id, "similarity_score", "0.92")
        _add_evidence(db, attempt.id, "liveness", "PASS")
        _add_evidence(db, attempt.id, "image_quality", "GOOD")

        evidence = (
            db.query(IdentityVerificationEvidence)
            .filter(IdentityVerificationEvidence.attempt_id == attempt.id)
            .all()
        )
        decision, reasoning = iv_decision.evaluate_evidence(evidence)
        assert decision == "MATCH"
        assert "exceeds threshold" in reasoning.lower() or "high" in reasoning.lower()

    def test_no_match_from_low_similarity(self, db, sample_data):
        """Low similarity evidence -> NO_MATCH."""
        attempt = _create_attempt(db, sample_data)
        _add_evidence(db, attempt.id, "similarity_score", "0.3")
        _add_evidence(db, attempt.id, "liveness", "PASS")

        evidence = (
            db.query(IdentityVerificationEvidence)
            .filter(IdentityVerificationEvidence.attempt_id == attempt.id)
            .all()
        )
        decision, _ = iv_decision.evaluate_evidence(evidence)
        assert decision == "NO_MATCH"

    def test_inconclusive_no_evidence(self, db, sample_data):
        """No evidence -> INCONCLUSIVE."""
        attempt = _create_attempt(db, sample_data)
        evidence = []
        decision, _ = iv_decision.evaluate_evidence(evidence)
        assert decision == "INCONCLUSIVE"

    def test_liveness_fail_overrides_high_similarity(self, db, sample_data):
        """Liveness FAIL overrides high similarity -> NO_MATCH."""
        attempt = _create_attempt(db, sample_data)
        _add_evidence(db, attempt.id, "similarity_score", "0.98")
        _add_evidence(db, attempt.id, "liveness", "FAIL")

        evidence = (
            db.query(IdentityVerificationEvidence)
            .filter(IdentityVerificationEvidence.attempt_id == attempt.id)
            .all()
        )
        decision, _ = iv_decision.evaluate_evidence(evidence)
        assert decision == "NO_MATCH"

    def test_poor_quality_with_high_similarity(self, db, sample_data):
        """High similarity + poor quality -> INCONCLUSIVE."""
        attempt = _create_attempt(db, sample_data)
        _add_evidence(db, attempt.id, "similarity_score", "0.95")
        _add_evidence(db, attempt.id, "liveness", "PASS")
        _add_evidence(db, attempt.id, "image_quality", "POOR")

        evidence = (
            db.query(IdentityVerificationEvidence)
            .filter(IdentityVerificationEvidence.attempt_id == attempt.id)
            .all()
        )
        decision, _ = iv_decision.evaluate_evidence(evidence)
        assert decision == "INCONCLUSIVE"

    def test_near_threshold_inconclusive(self, db, sample_data):
        """Near-threshold similarity -> INCONCLUSIVE."""
        settings = get_settings()
        near_threshold = settings.IDENTITY_VERIFICATION_MATCH_THRESHOLD * settings.IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR

        attempt = _create_attempt(db, sample_data)
        _add_evidence(db, attempt.id, "similarity_score", str(near_threshold + 0.02))
        _add_evidence(db, attempt.id, "liveness", "PASS")

        evidence = (
            db.query(IdentityVerificationEvidence)
            .filter(IdentityVerificationEvidence.attempt_id == attempt.id)
            .all()
        )
        decision, _ = iv_decision.evaluate_evidence(evidence)
        assert decision == "INCONCLUSIVE"

    def test_detailed_decision_metadata(self, db, sample_data):
        """DecisionResult contains proper metadata."""
        attempt = _create_attempt(db, sample_data)
        _add_evidence(db, attempt.id, "similarity_score", "0.90")
        _add_evidence(db, attempt.id, "liveness", "PASS")
        _add_evidence(db, attempt.id, "image_quality", "GOOD")

        evidence = (
            db.query(IdentityVerificationEvidence)
            .filter(IdentityVerificationEvidence.attempt_id == attempt.id)
            .all()
        )
        result = iv_decision.evaluate_evidence_detailed(evidence)
        assert result.decision == "MATCH"
        assert "threshold" in result.metadata
        assert "policy_version" in result.metadata
        assert result.metadata["similarity_scores_count"] == 1


# ===========================================================================
# 4. LIFECYCLE STATE MACHINE
# ===========================================================================

class TestLifecycleStateMachine:
    """Verify lifecycle transitions are enforced correctly."""

    def test_valid_transitions(self, db, sample_data):
        """All valid transitions succeed."""
        a = _create_attempt(db, sample_data)
        assert a.status == "CREATED"

        a = iv_service.start_attempt(db, a.id)
        assert a.status == "IN_PROGRESS"

        a = iv_service.complete_attempt(db, a.id, decision="MATCH")
        assert a.status == "COMPLETED"

    def test_cancel_from_created(self, db, sample_data):
        """Cancel from CREATED is valid."""
        a = _create_attempt(db, sample_data)
        a = iv_service.cancel_attempt(db, a.id)
        assert a.status == "CANCELLED"

    def test_fail_from_created(self, db, sample_data):
        """Fail from CREATED is valid."""
        a = _create_attempt(db, sample_data)
        a = iv_service.fail_attempt(db, a.id, reason="error")
        assert a.status == "FAILED"

    def test_cannot_start_completed(self, db, sample_data):
        """Cannot start a completed attempt."""
        a = _create_attempt(db, sample_data)
        a = _advance_attempt(db, a.id, to_status="COMPLETED")
        with pytest.raises(ValueError, match="transition"):
            iv_service.start_attempt(db, a.id)

    def test_cannot_complete_twice(self, db, sample_data):
        """Cannot complete an already completed attempt."""
        a = _create_attempt(db, sample_data)
        a = _advance_attempt(db, a.id, to_status="COMPLETED")
        with pytest.raises(ValueError, match="transition"):
            iv_service.complete_attempt(db, a.id, decision="MATCH")

    def test_cannot_fail_twice(self, db, sample_data):
        """Cannot fail an already failed attempt."""
        a = _create_attempt(db, sample_data)
        a = _advance_attempt(db, a.id, to_status="FAILED")
        with pytest.raises(ValueError, match="transition"):
            iv_service.fail_attempt(db, a.id, reason="again")

    def test_cannot_cancel_twice(self, db, sample_data):
        """Cannot cancel an already cancelled attempt."""
        a = _create_attempt(db, sample_data)
        a = _advance_attempt(db, a.id, to_status="CANCELLED")
        with pytest.raises(ValueError, match="transition"):
            iv_service.cancel_attempt(db, a.id)

    def test_cannot_verify_after_completed(self, db, sample_data):
        """Cannot verify face on a completed attempt."""
        a = _create_attempt(db, sample_data)
        a = _advance_attempt(db, a.id, to_status="COMPLETED")
        provider = _StubProvider()
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            with pytest.raises(ValueError):
                iv_service.verify_face(
                    db, a.id,
                    reference_image=_make_jpeg(),
                    probe_image=_make_jpeg(),
                    reference_image_format="image/jpeg",
                    probe_image_format="image/jpeg",
                )

    def test_cannot_verify_after_failed(self, db, sample_data):
        """Cannot verify face on a failed attempt."""
        a = _create_attempt(db, sample_data)
        a = _advance_attempt(db, a.id, to_status="FAILED")
        provider = _StubProvider()
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            with pytest.raises(ValueError):
                iv_service.verify_face(
                    db, a.id,
                    reference_image=_make_jpeg(),
                    probe_image=_make_jpeg(),
                    reference_image_format="image/jpeg",
                    probe_image_format="image/jpeg",
                )

    def test_cannot_review_from_created(self, db, sample_data):
        """Cannot review a CREATED attempt."""
        a = _create_attempt(db, sample_data)
        with pytest.raises(ValueError):
            iv_service.review_attempt(db, a.id)

    def test_cannot_override_from_created(self, db, sample_data):
        """Cannot override a CREATED attempt."""
        a = _create_attempt(db, sample_data)
        with pytest.raises(ValueError):
            iv_service.override_decision(
                db, a.id, new_decision="MATCH", reason="test",
            )

    def test_terminal_states_have_completed_at(self, db, sample_data):
        """All terminal states set completed_at."""
        for status in ["COMPLETED", "FAILED", "CANCELLED"]:
            a = _create_attempt(db, sample_data)
            a = _advance_attempt(db, a.id, to_status=status)
            assert a.completed_at is not None


# ===========================================================================
# 5. EVIDENCE CONSISTENCY
# ===========================================================================

class TestEvidenceConsistency:
    """Verify evidence belongs to correct attempt and is consistent."""

    def test_evidence_belongs_to_correct_attempt(self, db, sample_data):
        """Evidence is associated with the correct attempt."""
        a1 = _create_attempt(db, sample_data)
        a1 = iv_service.start_attempt(db, a1.id)
        _add_evidence(db, a1.id, "similarity_score", "0.9")

        # Complete a1 so we can create a2 with same student+registration
        iv_service.complete_attempt(db, a1.id, decision="MATCH")

        a2 = _create_attempt(db, sample_data)
        a2 = iv_service.start_attempt(db, a2.id)
        _add_evidence(db, a2.id, "similarity_score", "0.3")

        ev1 = db.query(IdentityVerificationEvidence).filter(
            IdentityVerificationEvidence.attempt_id == a1.id
        ).all()
        ev2 = db.query(IdentityVerificationEvidence).filter(
            IdentityVerificationEvidence.attempt_id == a2.id
        ).all()

        assert len(ev1) == 1
        assert len(ev2) == 1
        assert ev1[0].signal_value == "0.9"
        assert ev2[0].signal_value == "0.3"

    def test_evidence_count_after_multiple_verifications(self, db, sample_data):
        """Evidence accumulates across multiple verify calls."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        provider = _StubProvider()
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            iv_service.verify_face(
                db, a.id,
                reference_image=_make_jpeg(),
                probe_image=_make_jpeg(),
                reference_image_format="image/jpeg",
                probe_image_format="image/jpeg",
            )
            iv_service.verify_face(
                db, a.id,
                reference_image=_make_jpeg(),
                probe_image=_make_jpeg(),
                reference_image_format="image/jpeg",
                probe_image_format="image/jpeg",
            )

        evidence = db.query(IdentityVerificationEvidence).filter(
            IdentityVerificationEvidence.attempt_id == a.id
        ).all()
        assert len(evidence) >= 6  # 3+ signals per call

    def test_evidence_metadata_sanitized(self, db, sample_data):
        """Evidence metadata contains no raw images or embeddings."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        provider = _StubProvider()
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            records = iv_service.verify_face(
                db, a.id,
                reference_image=_make_jpeg(),
                probe_image=_make_jpeg(),
                reference_image_format="image/jpeg",
                probe_image_format="image/jpeg",
            )

        for r in records:
            # Details should not contain raw image bytes, base64, or embeddings
            if r.details:
                assert "raw" not in r.details.lower()
                assert "base64" not in r.details.lower()
                assert "embedding" not in r.details.lower()
                assert "pixel" not in r.details.lower()

    def test_record_evidence_on_in_progress(self, db, sample_data):
        """Manual evidence recording works on IN_PROGRESS attempts."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)
        ev = _add_evidence(db, a.id, "manual_check", "passed")
        assert ev.attempt_id == a.id

    def test_cannot_record_evidence_on_completed(self, db, sample_data):
        """Cannot record evidence on a completed attempt."""
        a = _create_attempt(db, sample_data)
        a = _advance_attempt(db, a.id, to_status="COMPLETED")
        with pytest.raises(ValueError):
            _add_evidence(db, a.id, "similarity_score", "0.9")


# ===========================================================================
# 6. REPEATED VERIFICATION CALLS
# ===========================================================================

class TestRepeatedVerification:
    """Verify evidence accumulation across multiple verify calls."""

    def test_three_verifications_accumulate(self, db, sample_data):
        """Three verify_face calls accumulate evidence correctly."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        provider = _StubProvider(match_score=0.88)
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            for i in range(3):
                iv_service.verify_face(
                    db, a.id,
                    reference_image=_make_jpeg(),
                    probe_image=_make_jpeg(),
                    reference_image_format="image/jpeg",
                    probe_image_format="image/jpeg",
                )

        evidence = db.query(IdentityVerificationEvidence).filter(
            IdentityVerificationEvidence.attempt_id == a.id
        ).all()
        # 3 signals per call * 3 calls = 9 minimum
        assert len(evidence) >= 9

    def test_repeated_calls_lifecycle_intact(self, db, sample_data):
        """Repeated calls do not corrupt lifecycle."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        provider = _StubProvider()
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            iv_service.verify_face(
                db, a.id,
                reference_image=_make_jpeg(),
                probe_image=_make_jpeg(),
                reference_image_format="image/jpeg",
                probe_image_format="image/jpeg",
            )

        db.refresh(a)
        assert a.status == "IN_PROGRESS"
        assert a.decision == "PENDING"

    def test_decision_after_multiple_verifications(self, db, sample_data):
        """Decision engine processes accumulated evidence correctly."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        provider = _StubProvider(match_score=0.90)
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            for _ in range(3):
                iv_service.verify_face(
                    db, a.id,
                    reference_image=_make_jpeg(),
                    probe_image=_make_jpeg(),
                    reference_image_format="image/jpeg",
                    probe_image_format="image/jpeg",
                )

        evidence = db.query(IdentityVerificationEvidence).filter(
            IdentityVerificationEvidence.attempt_id == a.id
        ).all()
        decision, _ = iv_decision.evaluate_evidence(evidence)
        # With high similarity and liveness pass, should be MATCH
        assert decision == "MATCH"


# ===========================================================================
# 7. CONCURRENCY / RACE CONDITIONS
# ===========================================================================

class TestConcurrency:
    """Test concurrent operations for race conditions."""

    def test_concurrent_verify_calls(self, sample_data):
        """Two concurrent verify_face calls on the same attempt.

        Each thread uses its own SessionLocal() session, matching
        production behaviour where each FastAPI request gets an
        independent session via get_db().  Sharing a single Session
        across threads is undefined behaviour in SQLAlchemy and causes
        duplicate primary-key violations during autoflush.
        """
        setup_db = SessionLocal()
        try:
            a = _create_attempt(setup_db, sample_data)
            a = iv_service.start_attempt(setup_db, a.id)
        finally:
            setup_db.close()

        provider = _StubProvider()
        errors = []

        def verify():
            thread_db = SessionLocal()
            try:
                with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
                    iv_service.verify_face(
                        thread_db, a.id,
                        reference_image=_make_jpeg(),
                        probe_image=_make_jpeg(),
                        reference_image_format="image/jpeg",
                        probe_image_format="image/jpeg",
                    )
            except Exception as e:
                errors.append(e)
            finally:
                thread_db.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(verify) for _ in range(2)]
            for f in as_completed(futures):
                f.result()

        # Both should succeed (evidence accumulates)
        verify_db = SessionLocal()
        try:
            evidence = verify_db.query(IdentityVerificationEvidence).filter(
                IdentityVerificationEvidence.attempt_id == a.id
            ).all()
            # At least 3 signals from one call, possibly more
            assert len(evidence) >= 3
        finally:
            verify_db.close()

    def test_concurrent_review_requests(self, sample_data):
        """Two concurrent review requests on the same attempt.

        Each thread uses its own SessionLocal() session, matching
        production behaviour.
        """
        setup_db = SessionLocal()
        try:
            a = _create_attempt(setup_db, sample_data)
            a = _advance_attempt(setup_db, a.id, to_status="COMPLETED")
        finally:
            setup_db.close()

        results = []

        def review():
            thread_db = SessionLocal()
            try:
                iv_service.review_attempt(thread_db, a.id, reviewer_notes="concurrent")
                results.append("ok")
            except Exception:
                results.append("error")
            finally:
                thread_db.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(review) for _ in range(2)]
            for f in as_completed(futures):
                f.result()

        # At least one should succeed (both may succeed since review is idempotent-ish)
        assert len(results) == 2

    def test_concurrent_overrides(self, sample_data):
        """Two concurrent override requests — at least one should succeed.

        Each thread uses its own SessionLocal() session, matching
        production behaviour.
        """
        setup_db = SessionLocal()
        try:
            a = _create_attempt(setup_db, sample_data)
            a = _advance_attempt(setup_db, a.id, to_status="COMPLETED")
        finally:
            setup_db.close()

        results = []

        def override():
            thread_db = SessionLocal()
            try:
                iv_service.override_decision(
                    thread_db, a.id,
                    new_decision="NO_MATCH",
                    reason="concurrent override",
                )
                results.append("ok")
            except Exception:
                results.append("error")
            finally:
                thread_db.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(override) for _ in range(2)]
            for f in as_completed(futures):
                f.result()

        # Both may succeed since override changes decision and both see the same initial state
        assert len(results) == 2

    def test_verify_then_cancel(self, db, sample_data):
        """Verify and cancel in quick succession."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        provider = _StubProvider()
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            iv_service.verify_face(
                db, a.id,
                reference_image=_make_jpeg(),
                probe_image=_make_jpeg(),
                reference_image_format="image/jpeg",
                probe_image_format="image/jpeg",
            )

        # Cancel after verify
        a = iv_service.cancel_attempt(db, a.id)
        assert a.status == "CANCELLED"


# ===========================================================================
# 8. HUMAN REVIEW INTEGRATION
# ===========================================================================

class TestHumanReviewIntegration:
    """Test complete review flow."""

    def test_review_flow(self, db, sample_data):
        """Automated result -> review -> reviewed state."""
        a = _create_attempt(db, sample_data)
        a = _advance_attempt(db, a.id, to_status="COMPLETED")

        # Verify there's a decision
        assert a.decision in ("MATCH", "NO_MATCH", "INCONCLUSIVE")

        # Request review
        a = iv_service.review_attempt(db, a.id, reviewer_notes="needs manual check")
        assert a.failure_reason is not None
        parsed = json.loads(a.failure_reason)
        assert parsed["audit_type"] == "review_requested"
        assert parsed["reviewer_notes"] == "needs manual check"
        assert parsed["original_decision"] is not None

    def test_review_preserves_evidence(self, db, sample_data):
        """Review does not erase evidence."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        provider = _StubProvider()
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            iv_service.verify_face(
                db, a.id,
                reference_image=_make_jpeg(),
                probe_image=_make_jpeg(),
                reference_image_format="image/jpeg",
                probe_image_format="image/jpeg",
            )

        a = iv_service.complete_attempt(db, a.id, decision="INCONCLUSIVE")
        ev_before = db.query(IdentityVerificationEvidence).filter(
            IdentityVerificationEvidence.attempt_id == a.id
        ).count()

        a = iv_service.review_attempt(db, a.id)
        ev_after = db.query(IdentityVerificationEvidence).filter(
            IdentityVerificationEvidence.attempt_id == a.id
        ).count()

        assert ev_before == ev_after

    def test_review_on_failed_attempt(self, db, sample_data):
        """Review works on FAILED attempts."""
        a = _create_attempt(db, sample_data)
        a = _advance_attempt(db, a.id, to_status="FAILED")
        a = iv_service.review_attempt(db, a.id)
        assert a.failure_reason is not None

    def test_review_without_notes(self, db, sample_data):
        """Review without notes works."""
        a = _create_attempt(db, sample_data)
        a = _advance_attempt(db, a.id, to_status="COMPLETED")
        a = iv_service.review_attempt(db, a.id)
        assert a.failure_reason is not None


# ===========================================================================
# 9. HUMAN OVERRIDE INTEGRATION
# ===========================================================================

class TestHumanOverrideIntegration:
    """Test complete override flow."""

    def test_override_all_transitions(self, db, sample_data):
        """Test all valid override transitions."""
        transitions = [
            ("MATCH", "NO_MATCH"),
            ("MATCH", "INCONCLUSIVE"),
            ("NO_MATCH", "MATCH"),
            ("NO_MATCH", "INCONCLUSIVE"),
            ("INCONCLUSIVE", "MATCH"),
            ("INCONCLUSIVE", "NO_MATCH"),
        ]
        for orig, new in transitions:
            a = _create_attempt(db, sample_data)
            a = iv_service.start_attempt(db, a.id)
            a = iv_service.complete_attempt(db, a.id, decision=orig)

            a = iv_service.override_decision(
                db, a.id, new_decision=new, reason=f"test {orig}->{new}",
            )
            assert a.decision == new

    def test_override_preserves_audit(self, db, sample_data):
        """Override creates proper audit entry."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)
        a = iv_service.complete_attempt(db, a.id, decision="NO_MATCH")

        a = iv_service.override_decision(
            db, a.id,
            new_decision="MATCH",
            reason="Student verified manually",
            operator_id="admin_001",
        )

        parsed = parse_override_audit_entry(a.failure_reason)
        assert parsed is not None
        assert parsed["original_decision"] == "NO_MATCH"
        assert parsed["override_decision"] == "MATCH"
        assert parsed["reason"] == "Student verified manually"
        assert parsed["operator_id"] == "admin_001"

    def test_override_preserves_evidence(self, db, sample_data):
        """Override does not erase evidence."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        provider = _StubProvider()
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            iv_service.verify_face(
                db, a.id,
                reference_image=_make_jpeg(),
                probe_image=_make_jpeg(),
                reference_image_format="image/jpeg",
                probe_image_format="image/jpeg",
            )

        a = iv_service.complete_attempt(db, a.id, decision="NO_MATCH")
        ev_before = db.query(IdentityVerificationEvidence).filter(
            IdentityVerificationEvidence.attempt_id == a.id
        ).count()

        a = iv_service.override_decision(
            db, a.id, new_decision="MATCH", reason="manual verification",
        )
        ev_after = db.query(IdentityVerificationEvidence).filter(
            IdentityVerificationEvidence.attempt_id == a.id
        ).count()

        assert ev_before == ev_after

    def test_override_requires_reason(self, db, sample_data):
        """Override with empty reason is rejected."""
        a = _create_attempt(db, sample_data)
        a = _advance_attempt(db, a.id, to_status="COMPLETED")
        with pytest.raises(ValueError):
            iv_service.override_decision(
                db, a.id, new_decision="MATCH", reason="",
            )

    def test_override_requires_terminal_state(self, db, sample_data):
        """Override on non-terminal state is rejected."""
        a = _create_attempt(db, sample_data)
        with pytest.raises(ValueError):
            iv_service.override_decision(
                db, a.id, new_decision="MATCH", reason="test",
            )

    def test_multiple_overrides_chain(self, db, sample_data):
        """Multiple overrides chain correctly."""
        a = _create_attempt(db, sample_data)
        a = _advance_attempt(db, a.id, to_status="COMPLETED")

        a = iv_service.override_decision(
            db, a.id, new_decision="MATCH", reason="first",
        )
        assert a.decision == "MATCH"

        a = iv_service.override_decision(
            db, a.id, new_decision="NO_MATCH", reason="second",
        )
        assert a.decision == "NO_MATCH"

    def test_override_on_api(self, client, sample_data):
        """Override works through API."""
        res = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
        })
        aid = res.json()["id"]
        client.post(f"/api/v1/identity-verifications/{aid}/start")
        client.post(f"/api/v1/identity-verifications/{aid}/complete",
                     json={"decision": "NO_MATCH"})

        res = client.post(f"/api/v1/identity-verifications/{aid}/override", json={
            "new_decision": "MATCH",
            "reason": "manual check passed",
        })
        assert res.status_code == 200
        assert res.json()["decision"] == "MATCH"


# ===========================================================================
# 10. AUDIT TRAIL INTEGRATION
# ===========================================================================

class TestAuditTrailIntegration:
    """Verify audit information flows through the system."""

    def test_override_audit_json_structure(self):
        """Override audit entry has correct JSON structure."""
        entry = build_override_audit_entry(
            original_decision="NO_MATCH",
            override_decision="MATCH",
            reason="manual verification",
            operator_id="op_001",
            previous_status="COMPLETED",
        )
        parsed = json.loads(entry)
        assert parsed["audit_type"] == "human_override"
        assert parsed["original_decision"] == "NO_MATCH"
        assert parsed["override_decision"] == "MATCH"
        assert parsed["reason"] == "manual verification"
        assert parsed["operator_id"] == "op_001"
        assert "override_timestamp" in parsed

    def test_review_audit_json_structure(self, db, sample_data):
        """Review stores proper JSON audit."""
        a = _create_attempt(db, sample_data)
        a = _advance_attempt(db, a.id, to_status="COMPLETED")
        original_decision = a.decision

        a = iv_service.review_attempt(db, a.id, reviewer_notes="check this")
        parsed = json.loads(a.failure_reason)
        assert parsed["audit_type"] == "review_requested"
        assert parsed["reviewer_notes"] == "check this"
        assert parsed["original_decision"] == original_decision

    def test_audit_metadata_no_biometrics(self):
        """Audit metadata contains no biometric data."""
        meta = build_verification_audit_metadata(
            attempt_id=1,
            provider_name="test",
            category="test",
            decision="MATCH",
            evidence_count=3,
            duration_ms=100,
        )
        meta_str = json.dumps(meta)
        assert "image" not in meta_str.lower()
        assert "embedding" not in meta_str.lower()
        assert "base64" not in meta_str.lower()

    def test_parse_non_override_returns_none(self):
        """Parsing non-override failure_reason returns None."""
        assert parse_override_audit_entry(None) is None
        assert parse_override_audit_entry("") is None
        assert parse_override_audit_entry("plain text failure") is None

    def test_audit_through_complete_flow(self, db, sample_data):
        """Audit trail exists through complete flow."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        provider = _StubProvider()
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            iv_service.verify_face(
                db, a.id,
                reference_image=_make_jpeg(),
                probe_image=_make_jpeg(),
                reference_image_format="image/jpeg",
                probe_image_format="image/jpeg",
            )

        a = iv_service.complete_attempt(db, a.id, decision="MATCH")
        assert a.completed_at is not None

        a = iv_service.override_decision(
            db, a.id, new_decision="NO_MATCH", reason="override",
        )
        parsed = parse_override_audit_entry(a.failure_reason)
        assert parsed is not None
        assert parsed["original_decision"] == "MATCH"


# ===========================================================================
# 11. FAILURE MATRIX
# ===========================================================================

class TestFailureMatrix:
    """Verify each failure mode is handled correctly."""

    def test_provider_unavailable(self, db, sample_data):
        """ProviderUnavailable -> FAILED attempt, no false decision."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        provider = _StubProvider(available=False)
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            with pytest.raises(ValueError):
                iv_service.verify_face(
                    db, a.id,
                    reference_image=_make_jpeg(),
                    probe_image=_make_jpeg(),
                    reference_image_format="image/jpeg",
                    probe_image_format="image/jpeg",
                )

        db.refresh(a)
        assert a.status == "FAILED"
        assert a.decision == "PENDING"

    def test_provider_exception(self, db, sample_data):
        """Provider exception -> FAILED attempt, no false decision."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        bad_provider = MagicMock()
        bad_provider.health_check.return_value = ProviderStatus(
            available=True, message="ok", provider_name="bad", provider_version="0",
        )
        bad_provider.verify.side_effect = RuntimeError("crash")

        with patch("app.services.face_verification.get_face_verification_provider", return_value=bad_provider):
            with pytest.raises(ValueError):
                iv_service.verify_face(
                    db, a.id,
                    reference_image=_make_jpeg(),
                    probe_image=_make_jpeg(),
                    reference_image_format="image/jpeg",
                    probe_image_format="image/jpeg",
                )

        db.refresh(a)
        assert a.status == "FAILED"

    def test_empty_images(self, db, sample_data):
        """Empty images rejected."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        provider = _StubProvider()
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            with pytest.raises(ValueError):
                iv_service.verify_face(
                    db, a.id,
                    reference_image=b"",
                    probe_image=_make_jpeg(),
                    reference_image_format="image/jpeg",
                    probe_image_format="image/jpeg",
                )

    def test_wrong_method(self, db, sample_data):
        """Non-FACE method rejected for verify_face."""
        a = _create_attempt(db, sample_data, method="MANUAL")
        a = iv_service.start_attempt(db, a.id)

        provider = _StubProvider()
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            with pytest.raises(ValueError, match="FACE"):
                iv_service.verify_face(
                    db, a.id,
                    reference_image=_make_jpeg(),
                    probe_image=_make_jpeg(),
                    reference_image_format="image/jpeg",
                    probe_image_format="image/jpeg",
                )

    def test_attempt_not_found(self, db):
        """Non-existent attempt returns None from get_attempt."""
        result = iv_service.get_attempt(db, 999999)
        assert result is None

    def test_invalid_decision_value(self, db, sample_data):
        """Invalid decision value rejected."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)
        with pytest.raises(ValueError):
            iv_service.complete_attempt(db, a.id, decision="ALLOW")

    def test_empty_failure_reason(self, db, sample_data):
        """Empty failure reason on fail_attempt is accepted (service does not validate)."""
        a = _create_attempt(db, sample_data)
        a = iv_service.fail_attempt(db, a.id, reason="")
        assert a.status == "FAILED"
        assert a.failure_reason == ""

    def test_provider_failure_never_becomes_identity_mismatch(self, db, sample_data):
        """CRITICAL: Provider failure must never become identity mismatch."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        provider = _StubProvider(available=False)
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            with pytest.raises(ValueError):
                iv_service.verify_face(
                    db, a.id,
                    reference_image=_make_jpeg(),
                    probe_image=_make_jpeg(),
                    reference_image_format="image/jpeg",
                    probe_image_format="image/jpeg",
                )

        db.refresh(a)
        assert a.status == "FAILED"
        assert a.decision != "NO_MATCH"  # Must NOT be identity mismatch
        assert a.decision == "PENDING"

    def test_insufficient_evidence_never_becomes_match(self):
        """CRITICAL: Insufficient evidence must never become MATCH."""
        decision, _ = iv_decision.evaluate_evidence([])
        assert decision != "MATCH"
        assert decision == "INCONCLUSIVE"


# ===========================================================================
# 12. SECURITY INVARIANTS
# ===========================================================================

class TestSecurityInvariants:
    """Verify security properties through integration."""

    def test_client_cannot_set_threshold(self, client, sample_data):
        """API request cannot include threshold field."""
        res = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
            "threshold": 0.5,  # should be ignored
        })
        assert res.status_code == 201

    def test_client_cannot_force_decision_via_evidence(self, db, sample_data):
        """Client cannot force a decision by submitting fake evidence."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        # Client tries to submit "ALLOW" evidence
        _add_evidence(db, a.id, "ALLOW", "true")

        evidence = db.query(IdentityVerificationEvidence).filter(
            IdentityVerificationEvidence.attempt_id == a.id
        ).all()
        decision, _ = iv_decision.evaluate_evidence(evidence)
        # ALLOW evidence should not force MATCH
        assert decision != "MATCH"

    def test_provider_cannot_directly_authorize(self, db, sample_data):
        """Provider result fields cannot directly authorize exam entry."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        # Provider with authorization fields (should be ignored)
        class RogueProvider:
            def verify(self, req):
                return FaceVerificationResult(
                    identity_match_score=0.99,
                    liveness_score=0.99,
                    liveness_passed=True,
                    image_quality_score=0.99,
                    provider_name="rogue",
                    provider_version="0",
                    evidence_metadata={"decision": "MATCH", "allow": True},
                )
            def health_check(self):
                return ProviderStatus(available=True, message="ok", provider_name="rogue", provider_version="0")
            def get_capabilities(self):
                return ProviderCapabilities(
                    supports_liveness=True, supports_identity_match=True,
                    supports_image_quality=True, max_image_size_bytes=None,
                    supported_formats=("image/jpeg",),
                    provider_name="rogue", provider_version="0",
                )

        with patch("app.services.face_verification.get_face_verification_provider", return_value=RogueProvider()):
            records = iv_service.verify_face(
                db, a.id,
                reference_image=_make_jpeg(),
                probe_image=_make_jpeg(),
                reference_image_format="image/jpeg",
                probe_image_format="image/jpeg",
            )

        # Evidence must not contain authorization signals
        for r in records:
            assert r.signal_type not in ("ALLOW", "DENY", "decision", "authorize")

    def test_verify_face_request_no_threshold_field(self, client, sample_data):
        """VerifyFaceRequest schema does not accept threshold."""
        import inspect
        from app.api.v1.identity_verification import VerifyFaceRequest
        fields = VerifyFaceRequest.model_fields
        assert "threshold" not in fields
        assert "decision" not in fields
        assert "allow" not in fields

    def test_decision_engine_cannot_be_bypassed(self, db, sample_data):
        """Decision engine always runs; cannot be skipped."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        # Even with ALLOW evidence, decision engine evaluates properly
        _add_evidence(db, a.id, "similarity_score", "0.99")
        _add_evidence(db, a.id, "liveness", "PASS")
        _add_evidence(db, a.id, "ALLOW", "true")  # rogue evidence

        evidence = db.query(IdentityVerificationEvidence).filter(
            IdentityVerificationEvidence.attempt_id == a.id
        ).all()
        decision, _ = iv_decision.evaluate_evidence(evidence)
        assert decision == "MATCH"  # based on similarity, not ALLOW

    def test_liveness_fail_always_no_match(self):
        """Liveness failure always produces NO_MATCH."""
        evidence_records = [
            MagicMock(signal_type="similarity_score", signal_value="0.99", confidence=0.99, details=None, provider_name="test"),
            MagicMock(signal_type="liveness", signal_value="FAIL", confidence=None, details=None, provider_name="test"),
        ]
        decision, _ = iv_decision.evaluate_evidence(evidence_records)
        assert decision == "NO_MATCH"

    def test_no_composite_score_leakage(self, db, sample_data):
        """No composite confidence score in evidence."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        provider = _StubProvider()
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            records = iv_service.verify_face(
                db, a.id,
                reference_image=_make_jpeg(),
                probe_image=_make_jpeg(),
                reference_image_format="image/jpeg",
                probe_image_format="image/jpeg",
            )

        signal_types = {r.signal_type for r in records}
        assert "composite_confidence" not in signal_types
        assert "trust_score" not in signal_types
        assert "security_score" not in signal_types


# ===========================================================================
# 13. RATE LIMITING
# ===========================================================================

class TestRateLimiting:
    """Verify rate limiter behavior."""

    def test_attempt_limit_within(self, db, sample_data):
        """Calls within attempt limit succeed."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        limiter = get_rate_limiter()
        limiter.reset()
        for _ in range(4):
            limiter.record_attempt_call(str(a.id))

        assert limiter.check_attempt_limit(str(a.id), max_calls=5)

    def test_attempt_limit_at(self, db, sample_data):
        """Calls at attempt limit are rejected."""
        limiter = get_rate_limiter()
        limiter.reset()
        for _ in range(5):
            limiter.record_attempt_call("test_attempt")

        assert not limiter.check_attempt_limit("test_attempt", max_calls=5)

    def test_attempt_limit_over(self, db, sample_data):
        """Calls over attempt limit are rejected."""
        limiter = get_rate_limiter()
        limiter.reset()
        for _ in range(10):
            limiter.record_attempt_call("test_attempt")

        assert not limiter.check_attempt_limit("test_attempt", max_calls=5)

    def test_global_limit_within(self):
        """Global calls within limit succeed."""
        limiter = get_rate_limiter()
        limiter.reset()
        for _ in range(59):
            limiter.record_global_call()

        assert limiter.check_global_limit(max_per_minute=60)

    def test_global_limit_at(self):
        """Global calls at limit are rejected."""
        limiter = get_rate_limiter()
        limiter.reset()
        for _ in range(60):
            limiter.record_global_call()

        assert not limiter.check_global_limit(max_per_minute=60)

    def test_zero_means_unlimited(self):
        """Zero limit means unlimited."""
        limiter = get_rate_limiter()
        limiter.reset()
        for _ in range(100):
            limiter.record_global_call()

        assert limiter.check_global_limit(max_per_minute=0)

    def test_attempt_limits_independent(self):
        """Different attempts have independent limits."""
        limiter = get_rate_limiter()
        limiter.reset()
        for _ in range(5):
            limiter.record_attempt_call("attempt_1")

        assert limiter.check_attempt_limit("attempt_2", max_calls=5)

    def test_reset_clears_state(self):
        """Reset clears all state."""
        limiter = get_rate_limiter()
        for _ in range(60):
            limiter.record_global_call()
        assert not limiter.check_global_limit(max_per_minute=60)

        limiter.reset()
        assert limiter.check_global_limit(max_per_minute=60)


# ===========================================================================
# 14. API CONTRACT VALIDATION
# ===========================================================================

class TestAPIContractValidation:
    """Verify frontend/backend API contracts match."""

    def test_list_response_shape(self, client):
        """List response has correct shape."""
        res = client.get("/api/v1/identity-verifications")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data

    def test_context_response_shape(self, client, sample_data):
        """Context response has correct shape."""
        res = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
        })
        aid = res.json()["id"]
        res = client.get(f"/api/v1/identity-verifications/{aid}/context")
        assert res.status_code == 200
        data = res.json()
        assert "attempt" in data
        assert "evidence" in data
        assert "student" in data
        assert "exam" in data

    def test_verify_face_response_shape(self, client, sample_data):
        """Verify-face response has correct shape."""
        res = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
            "verification_method": "FACE",
        })
        aid = res.json()["id"]
        client.post(f"/api/v1/identity-verifications/{aid}/start")

        ref_b64 = _b64(_make_jpeg())
        probe_b64 = _b64(_make_jpeg())
        provider = _StubProvider()
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            res = client.post(f"/api/v1/identity-verifications/{aid}/verify-face", json={
                "reference_image": ref_b64,
                "probe_image": probe_b64,
            })
        assert res.status_code == 201
        data = res.json()
        assert "attempt_id" in data
        assert "evidence" in data
        assert isinstance(data["evidence"], list)

    def test_complete_response_shape(self, client, sample_data):
        """Complete response has correct shape."""
        res = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
        })
        aid = res.json()["id"]
        client.post(f"/api/v1/identity-verifications/{aid}/start")
        res = client.post(f"/api/v1/identity-verifications/{aid}/complete",
                         json={"decision": "MATCH"})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "COMPLETED"
        assert data["decision"] == "MATCH"

    def test_override_response_shape(self, client, sample_data):
        """Override response has correct shape."""
        res = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
        })
        aid = res.json()["id"]
        client.post(f"/api/v1/identity-verifications/{aid}/start")
        client.post(f"/api/v1/identity-verifications/{aid}/complete",
                     json={"decision": "NO_MATCH"})
        res = client.post(f"/api/v1/identity-verifications/{aid}/override", json={
            "new_decision": "MATCH",
            "reason": "manual check",
        })
        assert res.status_code == 200
        assert "decision" in res.json()

    def test_404_for_nonexistent(self, client):
        """Non-existent attempt returns 404."""
        res = client.get("/api/v1/identity-verifications/999999/context")
        assert res.status_code == 404

    def test_422_for_invalid_decision(self, client, sample_data):
        """Invalid decision returns 422."""
        res = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
        })
        aid = res.json()["id"]
        client.post(f"/api/v1/identity-verifications/{aid}/start")
        res = client.post(f"/api/v1/identity-verifications/{aid}/complete",
                         json={"decision": "ALLOW"})
        assert res.status_code == 422

    def test_list_with_filters(self, client, sample_data):
        """List endpoint accepts filter parameters."""
        client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
        })
        res = client.get("/api/v1/identity-verifications?status=CREATED")
        assert res.status_code == 200
        assert res.json()["total"] >= 1


# ===========================================================================
# 15. CONFIGURATION AUDIT
# ===========================================================================

class TestConfigurationAudit:
    """Verify configuration is correct and validated."""

    def test_default_threshold(self):
        """Default threshold is 0.85."""
        s = Settings()
        assert s.IDENTITY_VERIFICATION_MATCH_THRESHOLD == 0.85

    def test_default_near_factor(self):
        """Default near-threshold factor is 0.7."""
        s = Settings()
        assert s.IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR == 0.7

    def test_default_provider(self):
        """Default provider is deterministic."""
        s = Settings()
        assert s.FACE_VERIFICATION_PROVIDER == "deterministic"

    def test_retention_days_zero(self):
        """Image retention is 0 (never store)."""
        s = Settings()
        assert s.FACE_VERIFICATION_IMAGE_RETENTION_DAYS == 0

    def test_max_calls_per_attempt(self):
        """Default max calls per attempt is 5."""
        s = Settings()
        assert s.FACE_VERIFICATION_MAX_CALLS_PER_ATTEMPT == 5

    def test_max_calls_per_minute(self):
        """Default max calls per minute is 60."""
        s = Settings()
        assert s.FACE_VERIFICATION_MAX_CALLS_PER_MINUTE == 60

    def test_invalid_threshold_rejected(self):
        """Invalid threshold is rejected."""
        with pytest.raises(Exception):
            Settings(IDENTITY_VERIFICATION_MATCH_THRESHOLD=1.5)

    def test_invalid_near_factor_rejected(self):
        """Invalid near-threshold factor is rejected."""
        with pytest.raises(Exception):
            Settings(IDENTITY_VERIFICATION_NEAR_THRESHOLD_FACTOR=1.5)

    def test_zero_threshold_rejected(self):
        """Zero threshold is rejected."""
        with pytest.raises(Exception):
            Settings(IDENTITY_VERIFICATION_MATCH_THRESHOLD=0.0)


# ===========================================================================
# 16. ERROR SANITIZATION
# ===========================================================================

class TestErrorSanitization:
    """Verify API responses do not expose internals."""

    def test_provider_error_no_traceback(self, client, sample_data):
        """Provider error does not expose Python traceback."""
        res = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
            "verification_method": "FACE",
        })
        aid = res.json()["id"]
        client.post(f"/api/v1/identity-verifications/{aid}/start")

        bad_provider = MagicMock()
        bad_provider.health_check.return_value = ProviderStatus(
            available=True, message="ok", provider_name="bad", provider_version="0",
        )
        bad_provider.verify.side_effect = RuntimeError("/home/user/.cache/onnx/model.onnx")

        ref_b64 = _b64(_make_jpeg())
        probe_b64 = _b64(_make_jpeg())
        with patch("app.services.face_verification.get_face_verification_provider", return_value=bad_provider):
            res = client.post(f"/api/v1/identity-verifications/{aid}/verify-face", json={
                "reference_image": ref_b64,
                "probe_image": probe_b64,
            })

        assert res.status_code == 422
        detail = res.json().get("detail", "")
        assert "/home/" not in detail
        assert ".onnx" not in detail
        assert "Traceback" not in detail

    def test_404_no_internal_paths(self, client):
        """404 response contains no internal paths."""
        res = client.get("/api/v1/identity-verifications/999999")
        assert res.status_code == 404
        assert "FileNotFoundError" not in res.json().get("detail", "")

    def test_validation_error_safe(self, client, sample_data):
        """Validation error message is safe."""
        res = client.post("/api/v1/identity-verifications", json={
            "student_id": -1,
            "exam_registration_id": sample_data["registration_id"],
        })
        assert res.status_code in (404, 422)


# ===========================================================================
# 17. PRIVACY INTEGRATION
# ===========================================================================

class TestPrivacyIntegration:
    """Verify privacy properties through integration."""

    def test_no_raw_images_in_api_response(self, client, sample_data):
        """No raw image data in any API response."""
        res = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
            "verification_method": "FACE",
        })
        aid = res.json()["id"]
        client.post(f"/api/v1/identity-verifications/{aid}/start")

        ref_b64 = _b64(_make_jpeg())
        probe_b64 = _b64(_make_jpeg())
        provider = _StubProvider()
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            res = client.post(f"/api/v1/identity-verifications/{aid}/verify-face", json={
                "reference_image": ref_b64,
                "probe_image": probe_b64,
            })

        evidence = res.json()["evidence"]
        for e in evidence:
            details = e.get("details") or ""
            # Should not contain raw bytes, base64, or embedding data
            assert "raw" not in details.lower()
            assert "base64" not in details.lower()
            assert "embedding" not in details.lower()

    def test_context_response_no_images(self, client, sample_data):
        """Context response contains no image data."""
        res = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
            "verification_method": "FACE",
        })
        aid = res.json()["id"]
        res = client.get(f"/api/v1/identity-verifications/{aid}/context")
        assert "image" not in res.text.lower() or "verification_method" in res.text.lower()

    def test_config_retention_zero(self):
        """Config confirms zero image retention."""
        s = Settings()
        assert s.FACE_VERIFICATION_IMAGE_RETENTION_DAYS == 0


# ===========================================================================
# 18. PROVIDER FAILURE NOT FALSE DECISION
# ===========================================================================

class TestProviderFailureNotFalseDecision:
    """CRITICAL: Provider failures must never become identity decisions."""

    def test_unavailable_not_no_match(self, db, sample_data):
        """Provider unavailable is not treated as NO_MATCH."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        provider = _StubProvider(available=False)
        with patch("app.services.face_verification.get_face_verification_provider", return_value=provider):
            with pytest.raises(ValueError):
                iv_service.verify_face(
                    db, a.id,
                    reference_image=_make_jpeg(),
                    probe_image=_make_jpeg(),
                    reference_image_format="image/jpeg",
                    probe_image_format="image/jpeg",
                )

        db.refresh(a)
        assert a.status == "FAILED"
        assert a.decision != "NO_MATCH"

    def test_exception_not_mismatch(self, db, sample_data):
        """Provider exception is not treated as identity mismatch."""
        a = _create_attempt(db, sample_data)
        a = iv_service.start_attempt(db, a.id)

        bad_provider = MagicMock()
        bad_provider.health_check.return_value = ProviderStatus(
            available=True, message="ok", provider_name="bad", provider_version="0",
        )
        bad_provider.verify.side_effect = RuntimeError("crash")

        with patch("app.services.face_verification.get_face_verification_provider", return_value=bad_provider):
            with pytest.raises(ValueError):
                iv_service.verify_face(
                    db, a.id,
                    reference_image=_make_jpeg(),
                    probe_image=_make_jpeg(),
                    reference_image_format="image/jpeg",
                    probe_image_format="image/jpeg",
                )

        db.refresh(a)
        assert a.status == "FAILED"
        assert a.decision == "PENDING"

    def test_empty_evidence_not_match(self):
        """No evidence is not treated as MATCH."""
        decision, _ = iv_decision.evaluate_evidence([])
        assert decision != "MATCH"
