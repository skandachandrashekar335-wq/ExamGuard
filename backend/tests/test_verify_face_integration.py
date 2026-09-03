"""Integration tests for face verification wiring (Phase 8.2).

Tests verify:
- verify_face service function: evidence mapping, provider integration, failure semantics
- verify-face API endpoint: request/response flow, base64 handling
- Provider failures → attempt failure (not evidence)
- Verification results → evidence records (decision engine decides later)
- No biometric data stored, no raw images, no hard-coded thresholds
- Existing Phase 7 behavior remains intact
"""

import base64
import json
import pytest
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationDecision,
    IdentityVerificationEvidence,
    IdentityVerificationMethod,
    IdentityVerificationStatus,
)
from app.services.face_verification import (
    DeterministicProvider,
    FaceVerificationError,
    FaceVerificationErrorType,
    FaceVerificationRequest,
    FaceVerificationResult,
    ProviderStatus,
    ProviderUnavailableError,
)
from app.services.identity_verification import (
    cancel_attempt,
    complete_attempt,
    create_attempt,
    fail_attempt,
    get_attempt,
    record_evidence,
    start_attempt,
    verify_face,
)
from app.schemas.identity_verification import (
    IdentityVerificationCreate,
    IdentityVerificationEvidenceCreate,
)


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
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("VF%"))
            )
        ))
        db.execute(delete(Student).where(Student.usn.ilike("VF%")))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("VF%")))
        db.execute(delete(Subject).where(Subject.code.ilike("VF%")))
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
def sample_data():
    """Create test data for API tests, cleaned up by the cleanup fixture."""
    from app.models.exam import Exam
    from app.models.exam_registration import ExamRegistration, RegistrationStatus
    from app.models.student import Student
    from app.models.subject import Subject

    db = SessionLocal()
    try:
        subject = Subject(
            code="VF101", name="VF Subject", department="VF Dept",
            semester=1, credits=3,
        )
        db.add(subject)
        db.commit()
        db.refresh(subject)

        exam = Exam(
            subject_id=subject.id, exam_name="VF Exam Final",
            exam_date="2026-12-01", start_time="09:00", end_time="12:00",
            semester=1, department="VF Dept",
        )
        db.add(exam)
        db.commit()
        db.refresh(exam)

        student = Student(usn="VF001", name="Verify Face Student")
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


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def student(db):
    from app.models.student import Student
    s = Student(usn="VF001", name="Verify Face Student")
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@pytest.fixture()
def subject(db):
    from app.models.subject import Subject
    s = Subject(
        code="VF101", name="VF Subject", department="VF Dept",
        semester=1, credits=3,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@pytest.fixture()
def exam(db, subject):
    from app.models.exam import Exam
    e = Exam(
        subject_id=subject.id, exam_name="VF Exam Final",
        exam_date="2026-12-01", start_time="09:00", end_time="12:00",
        semester=1, department="VF Dept",
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


@pytest.fixture()
def registration(db, student, exam):
    from app.models.exam_registration import ExamRegistration, RegistrationStatus
    r = ExamRegistration(
        student_id=student.id, exam_id=exam.id,
        status=RegistrationStatus.REGISTERED.value,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@pytest.fixture()
def face_attempt(db, student, registration):
    data = IdentityVerificationCreate(
        student_id=student.id,
        exam_registration_id=registration.id,
        verification_method="FACE",
    )
    return create_attempt(db, data)


@pytest.fixture()
def manual_attempt(db, student, registration):
    data = IdentityVerificationCreate(
        student_id=student.id,
        exam_registration_id=registration.id,
        verification_method="MANUAL",
    )
    return create_attempt(db, data)


@pytest.fixture()
def default_provider():
    return DeterministicProvider()


@pytest.fixture()
def unavailable_provider():
    return DeterministicProvider(available=False)


def _make_test_jpeg() -> bytes:
    """Create a minimal valid JPEG for testing."""
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[25:75, 25:75] = (200, 180, 160)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


FAKE_REF_IMAGE_BYTES = _make_test_jpeg()
FAKE_PROBE_IMAGE_BYTES = _make_test_jpeg()
FAKE_REF_IMAGE = base64.b64encode(FAKE_REF_IMAGE_BYTES).decode()
FAKE_PROBE_IMAGE = base64.b64encode(FAKE_PROBE_IMAGE_BYTES).decode()


# ─── Service: Happy Path ────────────────────────────────────────────────

class TestVerifyFaceHappyPath:
    """Verify the happy path: provider produces evidence, evidence is persisted."""

    def test_returns_evidence_records(
        self, db, face_attempt, default_provider
    ):
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=default_provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )
        assert len(records) >= 1
        assert all(isinstance(r, IdentityVerificationEvidence) for r in records)

    def test_persists_evidence_in_database(
        self, db, face_attempt, default_provider
    ):
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=default_provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )
        db_records = (
            db.query(IdentityVerificationEvidence)
            .filter(IdentityVerificationEvidence.attempt_id == face_attempt.id)
            .all()
        )
        assert len(db_records) == len(records)

    def test_attempt_stays_in_progress(
        self, db, face_attempt, default_provider
    ):
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=default_provider,
        ):
            verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )
        attempt = get_attempt(db, face_attempt.id)
        assert attempt.status == IdentityVerificationStatus.IN_PROGRESS.value

    def test_evidence_has_provider_info(
        self, db, face_attempt, default_provider
    ):
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=default_provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )
        for record in records:
            assert record.provider_name == "deterministic"
            assert record.provider_version == "0.1.0"

    def test_works_on_created_attempt(
        self, db, face_attempt, default_provider
    ):
        """verify_face should work on CREATED attempts (not just IN_PROGRESS)."""
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=default_provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )
        assert len(records) >= 1


# ─── Service: Evidence Mapping ──────────────────────────────────────────

class TestVerifyFaceEvidenceMapping:
    """Verify that provider output is correctly mapped to evidence records."""

    def test_identity_match_score_maps_to_similarity_score(
        self, db, face_attempt, default_provider
    ):
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=default_provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )
        similarity = [r for r in records if r.signal_type == "similarity_score"]
        assert len(similarity) == 1
        assert similarity[0].confidence == 0.92
        assert similarity[0].signal_value == "0.92"

    def test_liveness_score_maps_to_liveness_score(
        self, db, face_attempt, default_provider
    ):
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=default_provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )
        liveness = [r for r in records if r.signal_type == "liveness_score"]
        assert len(liveness) == 1
        assert liveness[0].confidence == 0.95

    def test_liveness_passed_maps_to_liveness_signal(
        self, db, face_attempt, default_provider
    ):
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=default_provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )
        liveness = [r for r in records if r.signal_type == "liveness"]
        assert len(liveness) == 1
        assert liveness[0].signal_value == "PASS"

    def test_liveness_failed_maps_to_fail(
        self, db, face_attempt
    ):
        provider = DeterministicProvider(liveness_passed=False)
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )
        liveness = [r for r in records if r.signal_type == "liveness"]
        assert len(liveness) == 1
        assert liveness[0].signal_value == "FAIL"

    def test_image_quality_maps_to_good(
        self, db, face_attempt
    ):
        provider = DeterministicProvider(image_quality_score=0.85)
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )
        quality = [r for r in records if r.signal_type == "image_quality"]
        assert len(quality) == 1
        assert quality[0].signal_value == "GOOD"

    def test_image_quality_maps_to_poor(
        self, db, face_attempt
    ):
        provider = DeterministicProvider(image_quality_score=0.3)
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )
        quality = [r for r in records if r.signal_type == "image_quality"]
        assert len(quality) == 1
        assert quality[0].signal_value == "POOR"

    def test_none_scores_produce_no_evidence(
        self, db, face_attempt
    ):
        provider = DeterministicProvider(
            identity_match_score=None,
            liveness_score=None,
            liveness_passed=None,
            image_quality_score=None,
        )
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )
        assert len(records) == 0

    def test_evidence_details_are_json(
        self, db, face_attempt, default_provider
    ):
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=default_provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )
        for record in records:
            if record.details:
                parsed = json.loads(record.details)
                assert "source" in parsed
                assert parsed["source"] == "face_verification_provider"


# ─── Service: Failure Semantics ─────────────────────────────────────────

class TestVerifyFaceFailures:
    """Verify that provider failures fail the attempt (not produce evidence)."""

    def test_attempt_not_found(self, db):
        with pytest.raises(LookupError, match="not found"):
            verify_face(db, 99999, reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES)

    def test_wrong_status_completed(
        self, db, face_attempt, default_provider
    ):
        start_attempt(db, face_attempt.id)
        complete_attempt(db, face_attempt.id, decision="MATCH")
        with pytest.raises(ValueError, match="CREATED or IN_PROGRESS"):
            verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )

    def test_wrong_status_failed(
        self, db, face_attempt
    ):
        start_attempt(db, face_attempt.id)
        fail_attempt(db, face_attempt.id, reason="test failure")
        with pytest.raises(ValueError, match="CREATED or IN_PROGRESS"):
            verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )

    def test_wrong_status_cancelled(
        self, db, face_attempt
    ):
        start_attempt(db, face_attempt.id)
        cancel_attempt(db, face_attempt.id, reason="cancelled")
        with pytest.raises(ValueError, match="CREATED or IN_PROGRESS"):
            verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )

    def test_wrong_method(
        self, db, manual_attempt
    ):
        with pytest.raises(ValueError, match="FACE"):
            verify_face(
                db, manual_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )

    def test_empty_reference_image(
        self, db, face_attempt, default_provider
    ):
        with pytest.raises(ValueError, match="reference_image"):
            verify_face(
                db, face_attempt.id,
                reference_image=b"", probe_image=b"probe",
            )

    def test_empty_probe_image(
        self, db, face_attempt, default_provider
    ):
        with pytest.raises(ValueError, match="probe_image"):
            verify_face(
                db, face_attempt.id,
                reference_image=b"ref", probe_image=b"",
            )

    def test_provider_unavailable_fails_attempt(
        self, db, face_attempt
    ):
        provider = DeterministicProvider(available=False)
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            with pytest.raises(ValueError, match="unavailable"):
                verify_face(
                    db, face_attempt.id,
                    reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
                )
        attempt = get_attempt(db, face_attempt.id)
        assert attempt.status == IdentityVerificationStatus.FAILED.value

    def test_provider_error_fails_attempt(
        self, db, face_attempt
    ):
        error = FaceVerificationError(
            error_type=FaceVerificationErrorType.TIMEOUT,
            message="Provider timed out",
        )
        provider = DeterministicProvider()
        with patch.object(provider, "verify", side_effect=ProviderUnavailableError(error)):
            start_attempt(db, face_attempt.id)
            with patch(
                "app.services.face_verification.get_face_verification_provider",
                return_value=provider,
            ):
                with pytest.raises(ValueError, match="Provider error"):
                    verify_face(
                        db, face_attempt.id,
                        reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
                    )
        attempt = get_attempt(db, face_attempt.id)
        assert attempt.status == IdentityVerificationStatus.FAILED.value


# ─── Service: No Sensitive Data ─────────────────────────────────────────

class TestVerifyFaceSensitiveData:
    """Verify that no biometric data or raw images are stored."""

    def test_no_raw_images_in_evidence(
        self, db, face_attempt, default_provider
    ):
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=default_provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )
        for record in records:
            assert record.details is None or len(record.details) < 10000
            if record.details:
                parsed = json.loads(record.details)
                for key, value in parsed.items():
                    assert not isinstance(value, bytes)

    def test_provider_result_has_no_raw_images(
        self, db, face_attempt, default_provider
    ):
        """Provider result should never contain raw image bytes."""
        request = FaceVerificationRequest(
            reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
        )
        result = default_provider.verify(request)
        result_dict = vars(result)
        for key, value in result_dict.items():
            assert not isinstance(value, bytes), (
                f"Provider result field '{key}' contains raw bytes"
            )


# ─── Service: Evidence ≠ Decision ───────────────────────────────────────

class TestVerifyFaceEvidenceNotDecision:
    """Verify that verify_face produces evidence, not decisions."""

    def test_verify_face_does_not_complete_attempt(
        self, db, face_attempt, default_provider
    ):
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=default_provider,
        ):
            verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )
        attempt = get_attempt(db, face_attempt.id)
        assert attempt.decision == IdentityVerificationDecision.PENDING.value

    def test_evidence_signals_are_continuous_values(
        self, db, face_attempt, default_provider
    ):
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=default_provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )
        for record in records:
            if record.confidence is not None:
                assert 0.0 <= record.confidence <= 1.0

    def test_decision_engine_can_process_provider_evidence(
        self, db, face_attempt, default_provider
    ):
        """After verify_face, the decision engine should work on the evidence."""
        from app.services.identity_verification_decision import evaluate_evidence

        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=default_provider,
        ):
            verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )
        evidence = (
            db.query(IdentityVerificationEvidence)
            .filter(IdentityVerificationEvidence.attempt_id == face_attempt.id)
            .all()
        )
        decision, reasoning = evaluate_evidence(evidence)
        assert decision in ("MATCH", "NO_MATCH", "INCONCLUSIVE")
        assert isinstance(reasoning, str)


# ─── Service: Multiple Calls ────────────────────────────────────────────

class TestVerifyFaceMultipleCalls:
    """Verify behavior when verify_face is called multiple times on same attempt."""

    def test_multiple_calls_accumulate_evidence(
        self, db, face_attempt, default_provider
    ):
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=default_provider,
        ):
            records1 = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )
            records2 = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_REF_IMAGE_BYTES, probe_image=FAKE_PROBE_IMAGE_BYTES,
            )
        total = (
            db.query(IdentityVerificationEvidence)
            .filter(IdentityVerificationEvidence.attempt_id == face_attempt.id)
            .count()
        )
        assert total == len(records1) + len(records2)


# ─── API: Happy Path ────────────────────────────────────────────────────

class TestVerifyFaceAPIHappyPath:
    """Verify the verify-face API endpoint happy path."""

    def test_verify_face_returns_201(
        self, client, sample_data, default_provider
    ):
        # Create and start attempt
        create_resp = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
            "verification_method": "FACE",
        })
        assert create_resp.status_code == 201
        attempt_id = create_resp.json()["id"]

        start_resp = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/start"
        )
        assert start_resp.status_code == 200

        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=default_provider,
        ):
            resp = client.post(
                f"/api/v1/identity-verifications/{attempt_id}/verify-face",
                json={
                    "reference_image": FAKE_REF_IMAGE,
                    "probe_image": FAKE_PROBE_IMAGE,
                },
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["attempt_id"] == attempt_id
        assert isinstance(body["evidence"], list)
        assert len(body["evidence"]) >= 1

    def test_verify_face_response_has_correct_fields(
        self, client, sample_data, default_provider
    ):
        create_resp = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
            "verification_method": "FACE",
        })
        attempt_id = create_resp.json()["id"]
        client.post(f"/api/v1/identity-verifications/{attempt_id}/start")

        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=default_provider,
        ):
            resp = client.post(
                f"/api/v1/identity-verifications/{attempt_id}/verify-face",
                json={
                    "reference_image": FAKE_REF_IMAGE,
                    "probe_image": FAKE_PROBE_IMAGE,
                },
            )
        body = resp.json()
        assert "attempt_id" in body
        assert "evidence" in body
        for ev in body["evidence"]:
            assert "signal_type" in ev
            assert "confidence" in ev
            assert "provider_name" in ev


# ─── API: Error Cases ───────────────────────────────────────────────────

class TestVerifyFaceAPIErrors:
    """Verify error handling in the verify-face API endpoint."""

    def test_invalid_base64_returns_422(self, client, sample_data):
        create_resp = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
            "verification_method": "FACE",
        })
        attempt_id = create_resp.json()["id"]
        client.post(f"/api/v1/identity-verifications/{attempt_id}/start")

        resp = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/verify-face",
            json={
                "reference_image": "not-valid-base64!!!",
                "probe_image": FAKE_PROBE_IMAGE,
            },
        )
        assert resp.status_code == 422

    def test_attempt_not_found_returns_404(self, client):
        resp = client.post(
            "/api/v1/identity-verifications/99999/verify-face",
            json={
                "reference_image": FAKE_REF_IMAGE,
                "probe_image": FAKE_PROBE_IMAGE,
            },
        )
        assert resp.status_code == 404

    def test_wrong_status_returns_422(
        self, client, sample_data, default_provider
    ):
        create_resp = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
            "verification_method": "FACE",
        })
        attempt_id = create_resp.json()["id"]
        client.post(f"/api/v1/identity-verifications/{attempt_id}/start")
        client.post(
            f"/api/v1/identity-verifications/{attempt_id}/complete",
            json={"decision": "MATCH"},
        )

        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=default_provider,
        ):
            resp = client.post(
                f"/api/v1/identity-verifications/{attempt_id}/verify-face",
                json={
                    "reference_image": FAKE_REF_IMAGE,
                    "probe_image": FAKE_PROBE_IMAGE,
                },
            )
        assert resp.status_code == 422

    def test_wrong_method_returns_422(
        self, client, sample_data, default_provider
    ):
        create_resp = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
            "verification_method": "MANUAL",
        })
        attempt_id = create_resp.json()["id"]

        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=default_provider,
        ):
            resp = client.post(
                f"/api/v1/identity-verifications/{attempt_id}/verify-face",
                json={
                    "reference_image": FAKE_REF_IMAGE,
                    "probe_image": FAKE_PROBE_IMAGE,
                },
            )
        assert resp.status_code == 422


# ─── API: Provider Unavailable ──────────────────────────────────────────

class TestVerifyFaceAPIProviderUnavailable:
    """Verify provider unavailability is handled at API level."""

    def test_provider_unavailable_returns_422(
        self, client, sample_data
    ):
        create_resp = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
            "verification_method": "FACE",
        })
        attempt_id = create_resp.json()["id"]
        client.post(f"/api/v1/identity-verifications/{attempt_id}/start")

        provider = DeterministicProvider(available=False)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            resp = client.post(
                f"/api/v1/identity-verifications/{attempt_id}/verify-face",
                json={
                    "reference_image": FAKE_REF_IMAGE,
                    "probe_image": FAKE_PROBE_IMAGE,
                },
            )
        assert resp.status_code == 422
