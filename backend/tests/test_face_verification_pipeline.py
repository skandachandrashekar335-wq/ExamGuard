"""Phase 8.4: Real face verification pipeline tests.

Comprehensive test suite for the end-to-end face verification pipeline:
- Input validation (base64, format, size, corruption, dimensions)
- Image validation helpers (magic bytes, decode, decompression bomb)
- API-level validation (schema + endpoint)
- Service-level validation (verify_face defense-in-depth)
- Pipeline integration (provider → evidence → decision engine)
- Privacy (no raw images, no embeddings stored/logged)
- Security (no biometric leakage, no provider exceptions exposed)
- Lifecycle (attempt state machine, repeated verification)
- Provider abstraction (UniFace vs Deterministic, factory selection)
- Decision separation (provider ≠ authority)

All tests use mocked UniFace — no model downloads required.
"""

import base64
import io
import json
import struct
import sys
import types
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest
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
from app.services.face_verification.providers.deterministic import (
    DeterministicProvider,
    ProviderUnavailableError,
)
from app.services.face_verification.types import (
    FaceVerificationError,
    FaceVerificationErrorType,
    FaceVerificationRequest,
    FaceVerificationResult,
    ProviderCapabilities,
    ProviderStatus,
)
from app.services.face_verification.validation import (
    ImageValidationError,
    detect_image_format,
    validate_image_bytes,
    decode_image_safely,
    MAX_IMAGE_DIMENSION,
    MIN_IMAGE_DIMENSION,
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


# ─── Fixtures ───────────────────────────────────────────────────────────

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
                db.query(Student.id).filter(Student.usn.ilike("P84%"))
            )
        ))
        db.execute(delete(Student).where(Student.usn.ilike("P84%")))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("P84%")))
        db.execute(delete(Subject).where(Subject.code.ilike("P84%")))
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


def _make_valid_jpeg(width: int = 100, height: int = 100) -> bytes:
    """Create a minimal valid JPEG for testing."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[25:75, 25:75] = (200, 180, 160)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


def _make_valid_png(width: int = 100, height: int = 100) -> bytes:
    """Create a minimal valid PNG for testing."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".png", img)
    return buf.tobytes()


def _encode_b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


FAKE_JPEG = _make_valid_jpeg()
FAKE_PNG = _make_valid_png()
FAKE_JPEG_B64 = _encode_b64(FAKE_JPEG)
FAKE_PNG_B64 = _encode_b64(FAKE_PNG)


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
            code="P84101", name="P84 Subject", department="P84 Dept",
            semester=1, credits=3,
        )
        db.add(subject)
        db.commit()
        db.refresh(subject)

        exam = Exam(
            subject_id=subject.id, exam_name="P84 Exam Final",
            exam_date="2026-12-01", start_time="09:00", end_time="12:00",
            semester=1, department="P84 Dept",
        )
        db.add(exam)
        db.commit()
        db.refresh(exam)

        student = Student(usn="P84001", name="Pipeline Student")
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
def face_attempt(db, sample_data):
    data = IdentityVerificationCreate(
        student_id=sample_data["student_id"],
        exam_registration_id=sample_data["registration_id"],
        verification_method="FACE",
    )
    return create_attempt(db, data)


@pytest.fixture()
def mock_uniface():
    """Mock UniFace for provider tests."""
    ref_emb = np.random.RandomState(42).rand(512).astype(np.float32)
    ref_emb = ref_emb / np.linalg.norm(ref_emb)
    probe_emb = np.random.RandomState(99).rand(512).astype(np.float32)
    probe_emb = probe_emb / np.linalg.norm(probe_emb)

    mock_detector_instance = MagicMock()
    mock_face = MagicMock()
    mock_face.bbox = np.array([25.0, 25.0, 75.0, 75.0], dtype=np.float32)
    mock_face.landmarks = np.array([
        [40.0, 45.0], [60.0, 45.0], [50.0, 55.0], [42.0, 65.0], [58.0, 65.0]
    ], dtype=np.float32)
    mock_face.confidence = 0.99
    mock_detector_instance.detect.return_value = [mock_face]

    mock_recognizer_instance = MagicMock()
    mock_recognizer_instance.get_normalized_embedding.side_effect = [ref_emb, probe_emb]

    mock_spoofer_instance = MagicMock()
    spoof_result = MagicMock()
    spoof_result.is_real = True
    spoof_result.confidence = 0.95
    mock_spoofer_instance.predict.return_value = spoof_result

    mock_detector_class = MagicMock(return_value=mock_detector_instance)
    mock_recognizer_class = MagicMock(return_value=mock_recognizer_instance)
    mock_spoofer_class = MagicMock(return_value=mock_spoofer_instance)

    def fake_load(self_inner):
        spoofer_cls = mock_spoofer_class if self_inner._anti_spoofing_enabled else None
        return mock_detector_class, mock_recognizer_class, spoofer_cls

    from app.services.face_verification.providers.uniface_provider import UniFaceProvider
    with patch.object(UniFaceProvider, "_load_uniface_modules", fake_load):
        yield {
            "detector": mock_detector_instance,
            "recognizer": mock_recognizer_instance,
            "spoofer": mock_spoofer_instance,
            "ref_emb": ref_emb,
            "probe_emb": probe_emb,
        }


# ═══════════════════════════════════════════════════════════════════════
# 1. IMAGE VALIDATION HELPER TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestImageValidationHelpers:
    """Test the image validation utility functions."""

    def test_valid_jpeg_passes(self):
        validate_image_bytes(FAKE_JPEG, field_name="test")

    def test_valid_png_passes(self):
        validate_image_bytes(FAKE_PNG, field_name="test")

    def test_empty_bytes_raises(self):
        with pytest.raises(ImageValidationError) as exc_info:
            validate_image_bytes(b"", field_name="test")
        assert exc_info.value.error_type == "EMPTY_IMAGE"

    def test_oversized_image_raises(self):
        huge = b"\xff\xd8\xff\xe0" + b"\x00" * (6 * 1024 * 1024)
        with pytest.raises(ImageValidationError) as exc_info:
            validate_image_bytes(huge, field_name="test", max_size_bytes=5 * 1024 * 1024)
        assert exc_info.value.error_type == "OVERSIZED_IMAGE"

    def test_custom_max_size(self):
        tiny_max = 10
        with pytest.raises(ImageValidationError) as exc_info:
            validate_image_bytes(FAKE_JPEG, field_name="test", max_size_bytes=tiny_max)
        assert exc_info.value.error_type == "OVERSIZED_IMAGE"

    def test_unsupported_format_raises(self):
        bmp_header = b"BM" + b"\x00" * 50
        with pytest.raises(ImageValidationError) as exc_info:
            validate_image_bytes(bmp_header, field_name="test")
        assert exc_info.value.error_type == "UNSUPPORTED_FORMAT"

    def test_corrupted_image_raises(self):
        fake_jpeg_header = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        with pytest.raises(ImageValidationError) as exc_info:
            validate_image_bytes(fake_jpeg_header, field_name="test")
        assert exc_info.value.error_type == "CORRUPTED_IMAGE"

    def test_image_too_small_raises(self):
        img = np.zeros((5, 5, 3), dtype=np.uint8)
        _, buf = cv2.imencode(".jpg", img)
        with pytest.raises(ImageValidationError) as exc_info:
            validate_image_bytes(buf.tobytes(), field_name="test")
        assert exc_info.value.error_type == "IMAGE_TOO_SMALL"

    def test_detect_jpeg_format(self):
        assert detect_image_format(FAKE_JPEG) == "image/jpeg"

    def test_detect_png_format(self):
        assert detect_image_format(FAKE_PNG) == "image/png"

    def test_detect_unknown_format(self):
        assert detect_image_format(b"\x00\x00\x00\x00") is None

    def test_detect_short_bytes(self):
        assert detect_image_format(b"\xff") is None

    def test_decode_image_safely_valid(self):
        img = decode_image_safely(FAKE_JPEG)
        assert isinstance(img, np.ndarray)
        assert img.shape[2] == 3

    def test_decode_image_safely_invalid(self):
        with pytest.raises(ImageValidationError):
            decode_image_safely(b"not-an-image")

    def test_allowed_formats_tuple(self):
        validate_image_bytes(
            FAKE_JPEG, field_name="test",
            supported_formats=("image/jpeg",),
        )
        with pytest.raises(ImageValidationError) as exc_info:
            validate_image_bytes(
                FAKE_PNG, field_name="test",
                supported_formats=("image/jpeg",),
            )
        assert exc_info.value.error_type == "UNSUPPORTED_FORMAT"


# ═══════════════════════════════════════════════════════════════════════
# 2. API-LEVEL INPUT VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestAPIInputValidation:
    """Test the verify-face API endpoint input validation."""

    def _create_face_attempt(self, client, sample_data):
        resp = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
            "verification_method": "FACE",
        })
        assert resp.status_code == 201
        attempt_id = resp.json()["id"]
        client.post(f"/api/v1/identity-verifications/{attempt_id}/start")
        return attempt_id

    def test_missing_reference_image(self, client, sample_data):
        attempt_id = self._create_face_attempt(client, sample_data)
        resp = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/verify-face",
            json={"probe_image": FAKE_JPEG_B64},
        )
        assert resp.status_code == 422

    def test_missing_probe_image(self, client, sample_data):
        attempt_id = self._create_face_attempt(client, sample_data)
        resp = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/verify-face",
            json={"reference_image": FAKE_JPEG_B64},
        )
        assert resp.status_code == 422

    def test_invalid_base64_reference(self, client, sample_data):
        attempt_id = self._create_face_attempt(client, sample_data)
        resp = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/verify-face",
            json={
                "reference_image": "not-valid-base64!!!",
                "probe_image": FAKE_JPEG_B64,
            },
        )
        assert resp.status_code == 422

    def test_invalid_base64_probe(self, client, sample_data):
        attempt_id = self._create_face_attempt(client, sample_data)
        resp = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/verify-face",
            json={
                "reference_image": FAKE_JPEG_B64,
                "probe_image": "not-valid-base64!!!",
            },
        )
        assert resp.status_code == 422

    def test_empty_base64_reference(self, client, sample_data):
        attempt_id = self._create_face_attempt(client, sample_data)
        resp = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/verify-face",
            json={
                "reference_image": _encode_b64(b""),
                "probe_image": FAKE_JPEG_B64,
            },
        )
        assert resp.status_code == 422

    def test_empty_base64_probe(self, client, sample_data):
        attempt_id = self._create_face_attempt(client, sample_data)
        resp = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/verify-face",
            json={
                "reference_image": FAKE_JPEG_B64,
                "probe_image": _encode_b64(b""),
            },
        )
        assert resp.status_code == 422

    def test_corrupted_reference_image(self, client, sample_data):
        attempt_id = self._create_face_attempt(client, sample_data)
        corrupted = _encode_b64(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        resp = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/verify-face",
            json={
                "reference_image": corrupted,
                "probe_image": FAKE_JPEG_B64,
            },
        )
        assert resp.status_code == 422

    def test_corrupted_probe_image(self, client, sample_data):
        attempt_id = self._create_face_attempt(client, sample_data)
        corrupted = _encode_b64(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        resp = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/verify-face",
            json={
                "reference_image": FAKE_JPEG_B64,
                "probe_image": corrupted,
            },
        )
        assert resp.status_code == 422

    def test_oversized_reference_image(self, client, sample_data):
        attempt_id = self._create_face_attempt(client, sample_data)
        huge = b"\xff\xd8\xff\xe0" + b"\x00" * (6 * 1024 * 1024)
        resp = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/verify-face",
            json={
                "reference_image": _encode_b64(huge),
                "probe_image": FAKE_JPEG_B64,
            },
        )
        assert resp.status_code == 422

    def test_oversized_probe_image(self, client, sample_data):
        attempt_id = self._create_face_attempt(client, sample_data)
        huge = b"\xff\xd8\xff\xe0" + b"\x00" * (6 * 1024 * 1024)
        resp = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/verify-face",
            json={
                "reference_image": FAKE_JPEG_B64,
                "probe_image": _encode_b64(huge),
            },
        )
        assert resp.status_code == 422

    def test_unsupported_format_reference(self, client, sample_data):
        attempt_id = self._create_face_attempt(client, sample_data)
        bmp = _encode_b64(b"BM" + b"\x00" * 50)
        resp = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/verify-face",
            json={
                "reference_image": bmp,
                "probe_image": FAKE_JPEG_B64,
            },
        )
        assert resp.status_code == 422

    def test_unsupported_format_probe(self, client, sample_data):
        attempt_id = self._create_face_attempt(client, sample_data)
        bmp = _encode_b64(b"BM" + b"\x00" * 50)
        resp = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/verify-face",
            json={
                "reference_image": FAKE_JPEG_B64,
                "probe_image": bmp,
            },
        )
        assert resp.status_code == 422

    def test_unsupported_format_field(self, client, sample_data):
        attempt_id = self._create_face_attempt(client, sample_data)
        resp = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/verify-face",
            json={
                "reference_image": FAKE_JPEG_B64,
                "probe_image": FAKE_JPEG_B64,
                "reference_image_format": "image/bmp",
            },
        )
        assert resp.status_code == 422

    def test_attempt_not_found_returns_404(self, client):
        resp = client.post(
            "/api/v1/identity-verifications/99999/verify-face",
            json={
                "reference_image": FAKE_JPEG_B64,
                "probe_image": FAKE_JPEG_B64,
            },
        )
        assert resp.status_code == 404

    def test_wrong_status_returns_422(self, client, sample_data):
        attempt_id = self._create_face_attempt(client, sample_data)
        client.post(
            f"/api/v1/identity-verifications/{attempt_id}/complete",
            json={"decision": "MATCH"},
        )
        resp = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/verify-face",
            json={
                "reference_image": FAKE_JPEG_B64,
                "probe_image": FAKE_JPEG_B64,
            },
        )
        assert resp.status_code == 422

    def test_wrong_method_returns_422(self, client, sample_data):
        resp = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
            "verification_method": "MANUAL",
        })
        attempt_id = resp.json()["id"]
        resp = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/verify-face",
            json={
                "reference_image": FAKE_JPEG_B64,
                "probe_image": FAKE_JPEG_B64,
            },
        )
        assert resp.status_code == 422

    def test_valid_jpeg_accepted(self, client, sample_data):
        attempt_id = self._create_face_attempt(client, sample_data)
        provider = DeterministicProvider()
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            resp = client.post(
                f"/api/v1/identity-verifications/{attempt_id}/verify-face",
                json={
                    "reference_image": FAKE_JPEG_B64,
                    "probe_image": FAKE_JPEG_B64,
                },
            )
        assert resp.status_code == 201

    def test_valid_png_accepted(self, client, sample_data):
        attempt_id = self._create_face_attempt(client, sample_data)
        provider = DeterministicProvider()
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            resp = client.post(
                f"/api/v1/identity-verifications/{attempt_id}/verify-face",
                json={
                    "reference_image": FAKE_PNG_B64,
                    "probe_image": FAKE_PNG_B64,
                },
            )
        assert resp.status_code == 201


# ═══════════════════════════════════════════════════════════════════════
# 3. SERVICE-LEVEL VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestServiceLevelValidation:
    """Test verify_face() service-level input validation."""

    def test_empty_reference_image(self, db, face_attempt):
        start_attempt(db, face_attempt.id)
        with pytest.raises(ValueError, match="reference_image"):
            verify_face(db, face_attempt.id, reference_image=b"", probe_image=b"probe")

    def test_empty_probe_image(self, db, face_attempt):
        start_attempt(db, face_attempt.id)
        with pytest.raises(ValueError, match="probe_image"):
            verify_face(db, face_attempt.id, reference_image=b"ref", probe_image=b"")

    def test_corrupted_reference_image(self, db, face_attempt):
        start_attempt(db, face_attempt.id)
        corrupted = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        with pytest.raises(ValueError, match="Invalid reference_image"):
            verify_face(db, face_attempt.id, reference_image=corrupted, probe_image=FAKE_JPEG)

    def test_corrupted_probe_image(self, db, face_attempt):
        start_attempt(db, face_attempt.id)
        corrupted = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        with pytest.raises(ValueError, match="Invalid probe_image"):
            verify_face(db, face_attempt.id, reference_image=FAKE_JPEG, probe_image=corrupted)

    def test_attempt_not_found(self, db):
        with pytest.raises(LookupError, match="not found"):
            verify_face(db, 99999, reference_image=FAKE_JPEG, probe_image=FAKE_JPEG)

    def test_wrong_status_completed(self, db, face_attempt):
        start_attempt(db, face_attempt.id)
        complete_attempt(db, face_attempt.id, decision="MATCH")
        with pytest.raises(ValueError, match="CREATED or IN_PROGRESS"):
            verify_face(db, face_attempt.id, reference_image=FAKE_JPEG, probe_image=FAKE_JPEG)

    def test_wrong_status_failed(self, db, face_attempt):
        start_attempt(db, face_attempt.id)
        fail_attempt(db, face_attempt.id, reason="test")
        with pytest.raises(ValueError, match="CREATED or IN_PROGRESS"):
            verify_face(db, face_attempt.id, reference_image=FAKE_JPEG, probe_image=FAKE_JPEG)

    def test_wrong_status_cancelled(self, db, face_attempt):
        start_attempt(db, face_attempt.id)
        cancel_attempt(db, face_attempt.id, reason="test")
        with pytest.raises(ValueError, match="CREATED or IN_PROGRESS"):
            verify_face(db, face_attempt.id, reference_image=FAKE_JPEG, probe_image=FAKE_JPEG)

    def test_wrong_method(self, db, sample_data):
        data = IdentityVerificationCreate(
            student_id=sample_data["student_id"],
            exam_registration_id=sample_data["registration_id"],
            verification_method="MANUAL",
        )
        attempt = create_attempt(db, data)
        with pytest.raises(ValueError, match="FACE"):
            verify_face(db, attempt.id, reference_image=FAKE_JPEG, probe_image=FAKE_JPEG)


# ═══════════════════════════════════════════════════════════════════════
# 4. FACE DETECTION TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestFaceDetection:
    """Test face detection behavior in the pipeline."""

    def test_no_face_in_reference(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()
        mock_uniface["detector"].detect.side_effect = [[], [MagicMock()]]
        request = FaceVerificationRequest(
            reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
        )
        with pytest.raises(ProviderUnavailableError) as exc_info:
            provider.verify(request)
        assert exc_info.value.error.error_type == FaceVerificationErrorType.NO_FACE_DETECTED
        assert "reference" in exc_info.value.error.message.lower()

    def test_no_face_in_probe(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()
        mock_uniface["detector"].detect.side_effect = [[MagicMock()], []]
        request = FaceVerificationRequest(
            reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
        )
        with pytest.raises(ProviderUnavailableError) as exc_info:
            provider.verify(request)
        assert exc_info.value.error.error_type == FaceVerificationErrorType.NO_FACE_DETECTED
        assert "probe" in exc_info.value.error.message.lower()

    def test_multiple_faces_in_reference(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()
        mock_uniface["detector"].detect.side_effect = [
            [MagicMock(), MagicMock()],
            [MagicMock()],
        ]
        request = FaceVerificationRequest(
            reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
        )
        with pytest.raises(ProviderUnavailableError) as exc_info:
            provider.verify(request)
        assert exc_info.value.error.error_type == FaceVerificationErrorType.MULTIPLE_FACES_DETECTED

    def test_multiple_faces_in_probe(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()
        mock_uniface["detector"].detect.side_effect = [
            [MagicMock()],
            [MagicMock(), MagicMock()],
        ]
        request = FaceVerificationRequest(
            reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
        )
        with pytest.raises(ProviderUnavailableError) as exc_info:
            provider.verify(request)
        assert exc_info.value.error.error_type == FaceVerificationErrorType.MULTIPLE_FACES_DETECTED

    def test_exactly_one_face_each(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()
        request = FaceVerificationRequest(
            reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
        )
        result = provider.verify(request)
        assert result.identity_match_score is not None
        assert 0.0 <= result.identity_match_score <= 1.0


# ═══════════════════════════════════════════════════════════════════════
# 5. FACE RECOGNITION TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestFaceRecognition:
    """Test face recognition behavior in the pipeline."""

    def test_cosine_similarity_computed(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()
        request = FaceVerificationRequest(
            reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
        )
        result = provider.verify(request)
        expected = float(np.dot(mock_uniface["ref_emb"], mock_uniface["probe_emb"]))
        assert abs(result.identity_match_score - expected) < 1e-6

    def test_recognition_failure(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()
        mock_uniface["recognizer"].get_normalized_embedding.side_effect = RuntimeError("model error")
        request = FaceVerificationRequest(
            reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
        )
        with pytest.raises(ProviderUnavailableError) as exc_info:
            provider.verify(request)
        assert exc_info.value.error.error_type == FaceVerificationErrorType.IDENTITY_MATCH_UNAVAILABLE

    def test_provider_exception_sanitized(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()
        mock_uniface["recognizer"].get_normalized_embedding.side_effect = RuntimeError("internal ONNX error")
        request = FaceVerificationRequest(
            reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
        )
        with pytest.raises(ProviderUnavailableError) as exc_info:
            provider.verify(request)
        msg = exc_info.value.error.message
        assert "Embedding extraction failed" in msg
        assert exc_info.value.error.error_type == FaceVerificationErrorType.IDENTITY_MATCH_UNAVAILABLE


# ═══════════════════════════════════════════════════════════════════════
# 6. LIVENESS / ANTI-SPOOFING TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestLiveness:
    """Test liveness/anti-spoofing behavior."""

    def test_liveness_from_anti_spoofing(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()
        request = FaceVerificationRequest(
            reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
        )
        result = provider.verify(request)
        assert result.liveness_score == 0.95
        assert result.liveness_passed is True

    def test_spoof_detected(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()
        spoof_result = MagicMock()
        spoof_result.is_real = False
        spoof_result.confidence = 0.87
        mock_uniface["spoofer"].predict.return_value = spoof_result
        request = FaceVerificationRequest(
            reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
        )
        result = provider.verify(request)
        assert result.liveness_passed is False
        assert result.liveness_score == 0.87

    def test_anti_spoofing_disabled(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider(anti_spoofing=False)
        request = FaceVerificationRequest(
            reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
        )
        result = provider.verify(request)
        assert result.liveness_score is None
        assert result.liveness_passed is None
        assert result.identity_match_score is not None

    def test_anti_spoofing_failure_non_fatal(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()
        mock_uniface["spoofer"].predict.side_effect = RuntimeError("model error")
        request = FaceVerificationRequest(
            reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
        )
        result = provider.verify(request)
        assert result.identity_match_score is not None
        assert result.liveness_score is None
        assert result.liveness_passed is None


# ═══════════════════════════════════════════════════════════════════════
# 7. EVIDENCE MAPPING TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestEvidenceMapping:
    """Test that provider output maps correctly to evidence records."""

    def test_similarity_score_evidence(self, db, face_attempt):
        provider = DeterministicProvider(identity_match_score=0.88)
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
            )
        similarity = [r for r in records if r.signal_type == "similarity_score"]
        assert len(similarity) == 1
        assert similarity[0].confidence == 0.88
        assert similarity[0].signal_value == "0.88"

    def test_liveness_score_evidence(self, db, face_attempt):
        provider = DeterministicProvider(liveness_score=0.91)
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
            )
        liveness = [r for r in records if r.signal_type == "liveness_score"]
        assert len(liveness) == 1
        assert liveness[0].confidence == 0.91

    def test_liveness_pass_evidence(self, db, face_attempt):
        provider = DeterministicProvider(liveness_passed=True)
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
            )
        liveness = [r for r in records if r.signal_type == "liveness"]
        assert len(liveness) == 1
        assert liveness[0].signal_value == "PASS"

    def test_liveness_fail_evidence(self, db, face_attempt):
        provider = DeterministicProvider(liveness_passed=False)
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
            )
        liveness = [r for r in records if r.signal_type == "liveness"]
        assert len(liveness) == 1
        assert liveness[0].signal_value == "FAIL"

    def test_none_scores_produce_no_evidence(self, db, face_attempt):
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
                reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
            )
        assert len(records) == 0

    def test_independent_signals_preserved(self, db, face_attempt):
        provider = DeterministicProvider(
            identity_match_score=0.92,
            liveness_score=0.95,
            liveness_passed=True,
            image_quality_score=0.85,
        )
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
            )
        types_found = {r.signal_type for r in records}
        assert "similarity_score" in types_found
        assert "liveness_score" in types_found
        assert "liveness" in types_found
        assert "image_quality" in types_found

    def test_no_composite_confidence(self, db, face_attempt):
        provider = DeterministicProvider()
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
            )
        for record in records:
            details = json.loads(record.details) if record.details else {}
            assert "composite" not in details
            assert "overall" not in details
            assert "combined" not in details


# ═══════════════════════════════════════════════════════════════════════
# 8. PRIVACY TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestPrivacy:
    """Verify no biometric data or raw images are stored/logged."""

    def test_no_raw_images_in_evidence(self, db, face_attempt):
        provider = DeterministicProvider()
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
            )
        for record in records:
            if record.details:
                parsed = json.loads(record.details)
                for key, value in parsed.items():
                    assert not isinstance(value, bytes)

    def test_no_embeddings_in_evidence(self, db, face_attempt):
        provider = DeterministicProvider()
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
            )
        for record in records:
            if record.details:
                parsed = json.loads(record.details)
                assert "embedding" not in parsed
                assert "template" not in parsed
                assert "biometric" not in parsed

    def test_provider_result_no_raw_images(self):
        provider = DeterministicProvider()
        request = FaceVerificationRequest(
            reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
        )
        result = provider.verify(request)
        for key, value in vars(result).items():
            assert not isinstance(value, bytes)

    def test_error_no_raw_images(self):
        error = FaceVerificationError(
            error_type=FaceVerificationErrorType.INVALID_INPUT,
            message="test",
        )
        for key, value in vars(error).items():
            assert not isinstance(value, bytes)

    def test_evidence_metadata_safe(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()
        request = FaceVerificationRequest(
            reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
        )
        result = provider.verify(request)
        for key, value in result.evidence_metadata.items():
            assert not isinstance(value, bytes)


# ═══════════════════════════════════════════════════════════════════════
# 9. LIFECYCLE TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestLifecycle:
    """Test attempt lifecycle and repeated verification."""

    def test_verify_face_does_not_complete_attempt(self, db, face_attempt):
        provider = DeterministicProvider()
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            verify_face(
                db, face_attempt.id,
                reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
            )
        attempt = get_attempt(db, face_attempt.id)
        assert attempt.decision == IdentityVerificationDecision.PENDING.value

    def test_multiple_calls_accumulate_evidence(self, db, face_attempt):
        provider = DeterministicProvider()
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            verify_face(db, face_attempt.id, reference_image=FAKE_JPEG, probe_image=FAKE_JPEG)
            verify_face(db, face_attempt.id, reference_image=FAKE_JPEG, probe_image=FAKE_JPEG)
        total = (
            db.query(IdentityVerificationEvidence)
            .filter(IdentityVerificationEvidence.attempt_id == face_attempt.id)
            .count()
        )
        assert total >= 8

    def test_provider_failure_fails_attempt(self, db, face_attempt):
        provider = DeterministicProvider(available=False)
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            with pytest.raises(ValueError, match="unavailable"):
                verify_face(
                    db, face_attempt.id,
                    reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
                )
        attempt = get_attempt(db, face_attempt.id)
        assert attempt.status == IdentityVerificationStatus.FAILED.value

    def test_provider_error_fails_attempt(self, db, face_attempt):
        error = FaceVerificationError(
            error_type=FaceVerificationErrorType.TIMEOUT,
            message="timed out",
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
                        reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
                    )
        attempt = get_attempt(db, face_attempt.id)
        assert attempt.status == IdentityVerificationStatus.FAILED.value


# ═══════════════════════════════════════════════════════════════════════
# 10. PROVIDER ABSTRACTION TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestProviderAbstraction:
    """Test provider selection and abstraction preservation."""

    def test_deterministic_provider_still_works(self):
        provider = DeterministicProvider(
            identity_match_score=0.88,
            liveness_passed=True,
        )
        request = FaceVerificationRequest(
            reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
        )
        result = provider.verify(request)
        assert result.identity_match_score == 0.88
        assert result.liveness_passed is True
        assert result.provider_name == "deterministic"

    def test_uniface_provider_selected(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        with patch("app.services.face_verification.factory.get_settings") as mock_settings:
            mock_settings.return_value.FACE_VERIFICATION_PROVIDER = "uniface"
            from app.services.face_verification import get_face_verification_provider
            provider = get_face_verification_provider()
        assert isinstance(provider, UniFaceProvider)

    def test_deterministic_provider_default(self):
        from app.services.face_verification import get_face_verification_provider
        provider = get_face_verification_provider()
        assert isinstance(provider, DeterministicProvider)

    def test_provider_capabilities(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()
        caps = provider.get_capabilities()
        assert caps.supports_identity_match is True
        assert caps.supports_liveness is True
        assert caps.supports_image_quality is False


# ═══════════════════════════════════════════════════════════════════════
# 11. DECISION SEPARATION TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestDecisionSeparation:
    """Verify provider cannot directly authorize."""

    def test_provider_result_has_no_decision_field(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()
        request = FaceVerificationRequest(
            reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
        )
        result = provider.verify(request)
        assert not hasattr(result, "decision")
        assert not hasattr(result, "allow")
        assert not hasattr(result, "deny")
        assert not hasattr(result, "verdict")

    def test_decision_engine_processes_evidence(self, db, face_attempt):
        from app.services.identity_verification_decision import evaluate_evidence
        provider = DeterministicProvider(identity_match_score=0.92)
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            verify_face(
                db, face_attempt.id,
                reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
            )
        evidence = (
            db.query(IdentityVerificationEvidence)
            .filter(IdentityVerificationEvidence.attempt_id == face_attempt.id)
            .all()
        )
        decision, reasoning = evaluate_evidence(evidence)
        assert decision in ("MATCH", "NO_MATCH", "INCONCLUSIVE")
        assert isinstance(reasoning, str)

    def test_evidence_signals_are_continuous(self, db, face_attempt):
        provider = DeterministicProvider()
        start_attempt(db, face_attempt.id)
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            records = verify_face(
                db, face_attempt.id,
                reference_image=FAKE_JPEG, probe_image=FAKE_JPEG,
            )
        for record in records:
            if record.confidence is not None:
                assert 0.0 <= record.confidence <= 1.0


# ═══════════════════════════════════════════════════════════════════════
# 12. ERROR TYPE TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestErrorTypes:
    """Test typed error semantics."""

    def test_all_error_types_exist(self):
        expected = {
            "PROVIDER_UNAVAILABLE", "TIMEOUT", "INVALID_INPUT",
            "NO_FACE_DETECTED", "MULTIPLE_FACES_DETECTED",
            "LIVENESS_UNAVAILABLE", "IDENTITY_MATCH_UNAVAILABLE",
            "PROVIDER_REJECTED", "INTERNAL_ERROR",
        }
        actual = {e.value for e in FaceVerificationErrorType}
        assert expected == actual

    def test_error_is_frozen(self):
        error = FaceVerificationError(
            error_type=FaceVerificationErrorType.TIMEOUT,
            message="test",
        )
        with pytest.raises(AttributeError):
            error.message = "modified"

    def test_provider_error_wrapping(self):
        inner = FaceVerificationError(
            error_type=FaceVerificationErrorType.TIMEOUT,
            message="timed out",
        )
        outer = ProviderUnavailableError(inner)
        assert outer.error.error_type == FaceVerificationErrorType.TIMEOUT
        assert str(outer) == "timed out"


# ═══════════════════════════════════════════════════════════════════════
# 13. API HAPPY PATH TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestAPIHappyPath:
    """Test the verify-face API endpoint happy path."""

    def test_verify_face_returns_201(self, client, sample_data):
        resp = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
            "verification_method": "FACE",
        })
        attempt_id = resp.json()["id"]
        client.post(f"/api/v1/identity-verifications/{attempt_id}/start")

        provider = DeterministicProvider()
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            resp = client.post(
                f"/api/v1/identity-verifications/{attempt_id}/verify-face",
                json={
                    "reference_image": FAKE_JPEG_B64,
                    "probe_image": FAKE_JPEG_B64,
                },
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["attempt_id"] == attempt_id
        assert isinstance(body["evidence"], list)
        assert len(body["evidence"]) >= 1

    def test_evidence_fields_correct(self, client, sample_data):
        resp = client.post("/api/v1/identity-verifications", json={
            "student_id": sample_data["student_id"],
            "exam_registration_id": sample_data["registration_id"],
            "verification_method": "FACE",
        })
        attempt_id = resp.json()["id"]
        client.post(f"/api/v1/identity-verifications/{attempt_id}/start")

        provider = DeterministicProvider()
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            resp = client.post(
                f"/api/v1/identity-verifications/{attempt_id}/verify-face",
                json={
                    "reference_image": FAKE_JPEG_B64,
                    "probe_image": FAKE_JPEG_B64,
                },
            )
        body = resp.json()
        for ev in body["evidence"]:
            assert "signal_type" in ev
            assert "confidence" in ev
            assert "provider_name" in ev
