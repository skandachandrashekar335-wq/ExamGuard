"""Tests for UniFace face verification provider (Phase 8.3).

Tests verify:
- Provider instantiation and capabilities
- Detection, recognition, anti-spoofing flow (mocked)
- Error handling: no face, multiple faces, invalid image
- Exception mapping to typed FaceVerificationError
- Privacy: no raw images in errors/results, no embeddings in metadata
- Provider does not make authorization decisions
- Factory correctly selects UniFace provider
- DeterministicProvider remains functional
- Existing Phase 8.1/8.2 tests remain intact

All tests use mocked UniFace models — no ML model downloads required.
"""

import sys
import types
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from app.services.face_verification.types import (
    FaceVerificationError,
    FaceVerificationErrorType,
    FaceVerificationRequest,
    FaceVerificationResult,
    ProviderCapabilities,
    ProviderStatus,
)
from app.services.face_verification.providers.deterministic import (
    DeterministicProvider,
    ProviderUnavailableError,
)
from app.services.face_verification.providers.uniface_provider import UniFaceProvider


# ─── Helpers ───────────────────────────────────────────────────────────

def _make_fake_jpeg(width: int = 100, height: int = 100) -> bytes:
    """Create a minimal valid JPEG byte string for testing."""
    import cv2
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[25:75, 25:75] = (200, 180, 160)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


def _make_mock_face(bbox=None, landmarks=None, confidence=0.99):
    """Create a mock UniFace face detection result."""
    face = MagicMock()
    face.bbox = bbox or np.array([25.0, 25.0, 75.0, 75.0], dtype=np.float32)
    face.landmarks = landmarks or np.array([
        [40.0, 45.0], [60.0, 45.0], [50.0, 55.0], [42.0, 65.0], [58.0, 65.0]
    ], dtype=np.float32)
    face.confidence = confidence
    return face


def _make_mock_spoof_result(is_real=True, confidence=0.95):
    """Create a mock UniFace anti-spoofing result."""
    result = MagicMock()
    result.is_real = is_real
    result.confidence = confidence
    return result


def _setup_mock_uniface_modules():
    """Install mock uniface modules into sys.modules.

    Creates a fake uniface package with detection/recognition/spoofing submodules.
    Used to satisfy import checks without real uniface.
    """
    uniface_pkg = types.ModuleType("uniface")
    uniface_pkg.__path__ = []

    detection_mod = types.ModuleType("uniface.detection")
    detection_mod.RetinaFace = MagicMock()

    recognition_mod = types.ModuleType("uniface.recognition")
    recognition_mod.ArcFace = MagicMock()

    spoofing_mod = types.ModuleType("uniface.spoofing")
    spoofing_mod.MiniFASNet = MagicMock()

    sys.modules["uniface"] = uniface_pkg
    sys.modules["uniface.detection"] = detection_mod
    sys.modules["uniface.recognition"] = recognition_mod
    sys.modules["uniface.spoofing"] = spoofing_mod

    uniface_pkg.detection = detection_mod
    uniface_pkg.recognition = recognition_mod
    uniface_pkg.spoofing = spoofing_mod

    modules = {
        "uniface": uniface_pkg,
        "uniface.detection": detection_mod,
        "uniface.recognition": recognition_mod,
        "uniface.spoofing": spoofing_mod,
    }
    return modules


@pytest.fixture
def sample_request() -> FaceVerificationRequest:
    return FaceVerificationRequest(
        reference_image=_make_fake_jpeg(),
        probe_image=_make_fake_jpeg(),
        reference_image_format="image/jpeg",
        probe_image_format="image/jpeg",
        context={"attempt_id": 1, "student_id": 42},
    )


@pytest.fixture
def mock_uniface():
    """Mock UniFace modules to avoid model downloads in tests.

    Patches _load_uniface_modules to return mock classes.
    _ensure_initialized instantiates them, getting our configured instances.
    """
    ref_emb = np.random.RandomState(42).rand(512).astype(np.float32)
    ref_emb = ref_emb / np.linalg.norm(ref_emb)
    probe_emb = np.random.RandomState(99).rand(512).astype(np.float32)
    probe_emb = probe_emb / np.linalg.norm(probe_emb)

    mock_detector_instance = MagicMock()
    mock_detector_instance.detect.return_value = [_make_mock_face()]

    mock_recognizer_instance = MagicMock()
    mock_recognizer_instance.get_normalized_embedding.side_effect = [ref_emb, probe_emb]

    mock_spoofer_instance = MagicMock()
    mock_spoofer_instance.predict.return_value = _make_mock_spoof_result()

    mock_detector_class = MagicMock(return_value=mock_detector_instance)
    mock_recognizer_class = MagicMock(return_value=mock_recognizer_instance)
    mock_spoofer_class = MagicMock(return_value=mock_spoofer_instance)

    def fake_load(self_inner):
        spoofer_cls = mock_spoofer_class if self_inner._anti_spoofing_enabled else None
        return mock_detector_class, mock_recognizer_class, spoofer_cls

    with patch.object(UniFaceProvider, "_load_uniface_modules", fake_load):
        yield {
            "detector": mock_detector_instance,
            "recognizer": mock_recognizer_instance,
            "spoofer": mock_spoofer_instance,
            "ref_emb": ref_emb,
            "probe_emb": probe_emb,
        }


# ─── Provider Instantiation ────────────────────────────────────────────

class TestUniFaceProviderInstantiation:
    """Verify provider can be instantiated and reports correct capabilities."""

    def test_import(self):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        assert UniFaceProvider is not None

    def test_capabilities(self):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()
        caps = provider.get_capabilities()
        assert isinstance(caps, ProviderCapabilities)
        assert caps.supports_identity_match is True
        assert caps.supports_liveness is True
        assert caps.supports_image_quality is False
        assert caps.provider_name == "uniface"
        assert "image/jpeg" in caps.supported_formats
        assert "image/png" in caps.supported_formats

    def test_capabilities_anti_spoofing_disabled(self):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider(anti_spoofing=False)
        caps = provider.get_capabilities()
        assert caps.supports_liveness is False


# ─── Successful Verification ───────────────────────────────────────────

class TestUniFaceVerification:
    """Verify the happy path: detection → recognition → anti-spoofing → evidence."""

    def test_returns_evidence_result(
        self, sample_request: FaceVerificationRequest, mock_uniface
    ):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()

        result = provider.verify(sample_request)

        assert isinstance(result, FaceVerificationResult)
        assert result.identity_match_score is not None
        assert 0.0 <= result.identity_match_score <= 1.0
        assert result.provider_name == "uniface"

    def test_identity_match_score_is_cosine_similarity(
        self, sample_request: FaceVerificationRequest, mock_uniface
    ):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()

        result = provider.verify(sample_request)

        expected_similarity = float(np.dot(mock_uniface["ref_emb"], mock_uniface["probe_emb"]))
        assert abs(result.identity_match_score - expected_similarity) < 1e-6

    def test_liveness_from_anti_spoofing(
        self, sample_request: FaceVerificationRequest, mock_uniface
    ):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()

        result = provider.verify(sample_request)

        assert result.liveness_score == 0.95
        assert result.liveness_passed is True

    def test_liveness_failed_when_spoof_detected(
        self, sample_request: FaceVerificationRequest, mock_uniface
    ):
        mock_uniface["spoofer"].predict.return_value = _make_mock_spoof_result(
            is_real=False, confidence=0.87
        )
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()

        result = provider.verify(sample_request)

        assert result.liveness_passed is False
        assert result.liveness_score == 0.87

    def test_anti_spoofing_disabled(
        self, sample_request: FaceVerificationRequest, mock_uniface
    ):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider(anti_spoofing=False)

        result = provider.verify(sample_request)

        assert result.liveness_score is None
        assert result.liveness_passed is None
        assert result.identity_match_score is not None

    def test_evidence_metadata_contains_provider_info(
        self, sample_request: FaceVerificationRequest, mock_uniface
    ):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()

        result = provider.verify(sample_request)

        assert result.evidence_metadata["source"] == "uniface_provider"
        assert "detection_model" in result.evidence_metadata
        assert "recognition_model" in result.evidence_metadata
        assert "anti_spoofing_enabled" in result.evidence_metadata


# ─── Face Detection Errors ─────────────────────────────────────────────

class TestUniFaceDetectionErrors:
    """Verify proper error handling for face detection issues."""

    def test_no_face_in_reference_image(
        self, sample_request: FaceVerificationRequest, mock_uniface
    ):
        mock_uniface["detector"].detect.side_effect = [[], [_make_mock_face()]]
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()

        with pytest.raises(ProviderUnavailableError) as exc_info:
            provider.verify(sample_request)
        assert exc_info.value.error.error_type == FaceVerificationErrorType.NO_FACE_DETECTED
        assert "reference" in exc_info.value.error.message.lower()

    def test_no_face_in_probe_image(
        self, sample_request: FaceVerificationRequest, mock_uniface
    ):
        mock_uniface["detector"].detect.side_effect = [[_make_mock_face()], []]
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()

        with pytest.raises(ProviderUnavailableError) as exc_info:
            provider.verify(sample_request)
        assert exc_info.value.error.error_type == FaceVerificationErrorType.NO_FACE_DETECTED
        assert "probe" in exc_info.value.error.message.lower()

    def test_multiple_faces_in_reference(
        self, sample_request: FaceVerificationRequest, mock_uniface
    ):
        mock_uniface["detector"].detect.side_effect = [
            [_make_mock_face(), _make_mock_face()],
            [_make_mock_face()],
        ]
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()

        with pytest.raises(ProviderUnavailableError) as exc_info:
            provider.verify(sample_request)
        assert exc_info.value.error.error_type == FaceVerificationErrorType.MULTIPLE_FACES_DETECTED

    def test_multiple_faces_in_probe(
        self, sample_request: FaceVerificationRequest, mock_uniface
    ):
        mock_uniface["detector"].detect.side_effect = [
            [_make_mock_face()],
            [_make_mock_face(), _make_mock_face()],
        ]
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()

        with pytest.raises(ProviderUnavailableError) as exc_info:
            provider.verify(sample_request)
        assert exc_info.value.error.error_type == FaceVerificationErrorType.MULTIPLE_FACES_DETECTED


# ─── Invalid Input ─────────────────────────────────────────────────────

class TestUniFaceInvalidInput:
    """Verify error handling for invalid images."""

    def test_invalid_reference_image(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()

        request = FaceVerificationRequest(
            reference_image=b"not-a-valid-image",
            probe_image=_make_fake_jpeg(),
        )
        with pytest.raises(ProviderUnavailableError) as exc_info:
            provider.verify(request)
        assert exc_info.value.error.error_type == FaceVerificationErrorType.INVALID_INPUT

    def test_invalid_probe_image(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()

        request = FaceVerificationRequest(
            reference_image=_make_fake_jpeg(),
            probe_image=b"not-a-valid-image",
        )
        with pytest.raises(ProviderUnavailableError) as exc_info:
            provider.verify(request)
        assert exc_info.value.error.error_type == FaceVerificationErrorType.INVALID_INPUT


# ─── Privacy ───────────────────────────────────────────────────────────

class TestUniFacePrivacy:
    """Verify no raw images or biometric data leak into results/errors."""

    def test_no_raw_images_in_result(
        self, sample_request: FaceVerificationRequest, mock_uniface
    ):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()

        result = provider.verify(sample_request)

        result_dict = vars(result)
        for key, value in result_dict.items():
            assert not isinstance(value, bytes), (
                f"Result field '{key}' contains raw bytes"
            )
            if isinstance(value, str) and len(value) > 1000:
                pytest.fail(f"Result field '{key}' contains unusually long string")

    def test_no_raw_images_in_error(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()

        request = FaceVerificationRequest(
            reference_image=b"bad",
            probe_image=b"bad",
        )
        try:
            provider.verify(request)
        except ProviderUnavailableError as e:
            error_dict = vars(e.error)
            for key, value in error_dict.items():
                assert not isinstance(value, bytes), (
                    f"Error field '{key}' contains raw bytes"
                )

    def test_no_embeddings_in_metadata(
        self, sample_request: FaceVerificationRequest, mock_uniface
    ):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()

        result = provider.verify(sample_request)

        metadata = result.evidence_metadata
        assert isinstance(metadata, dict)
        for key, value in metadata.items():
            assert not isinstance(value, bytes), f"Metadata field '{key}' contains raw bytes"
            if isinstance(value, np.ndarray):
                pytest.fail(f"Metadata field '{key}' contains numpy array (possible embedding)")


# ─── Provider Does Not Make Decisions ──────────────────────────────────

class TestUniFaceNoDecisions:
    """Verify the provider produces evidence, not authorization decisions."""

    def test_result_has_no_decision_field(
        self, sample_request: FaceVerificationRequest, mock_uniface
    ):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()

        result = provider.verify(sample_request)

        result_dict = vars(result)
        decision_fields = {"decision", "authorization", "allow", "deny", "verdict"}
        for field_name in decision_fields:
            assert field_name not in result_dict, (
                f"Result has field '{field_name}' — providers should produce evidence, not decisions"
            )

    def test_scores_are_continuous(
        self, sample_request: FaceVerificationRequest, mock_uniface
    ):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()

        result = provider.verify(sample_request)

        if result.identity_match_score is not None:
            assert isinstance(result.identity_match_score, float)
        if result.liveness_score is not None:
            assert isinstance(result.liveness_score, float)


# ─── Health Check ──────────────────────────────────────────────────────

class TestUniFaceHealthCheck:
    """Verify health check behavior."""

    def test_health_check_unavailable_without_init(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()
        provider._init_error = "uniface not installed"

        status = provider.health_check()
        assert isinstance(status, ProviderStatus)
        assert status.available is False

    def test_health_check_success(self, mock_uniface):
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()

        status = provider.health_check()
        assert status.available is True


# ─── Factory Selection ─────────────────────────────────────────────────

class TestUniFaceFactorySelection:
    """Verify factory correctly creates UniFaceProvider."""

    def test_factory_creates_uniface_provider(self):
        with patch("app.services.face_verification.factory.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(FACE_VERIFICATION_PROVIDER="uniface")
            from app.services.face_verification.factory import get_face_verification_provider
            provider = get_face_verification_provider()
            assert type(provider).__name__ == "UniFaceProvider"

    def test_factory_still_creates_deterministic(self):
        with patch("app.services.face_verification.factory.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(FACE_VERIFICATION_PROVIDER="deterministic")
            from app.services.face_verification.factory import get_face_verification_provider
            provider = get_face_verification_provider()
            assert isinstance(provider, DeterministicProvider)


# ─── DeterministicProvider Still Works ─────────────────────────────────

class TestDeterministicProviderStillWorks:
    """Verify the existing DeterministicProvider is not broken by Phase 8.3."""

    def test_deterministic_provider_returns_configured_scores(self):
        provider = DeterministicProvider(
            identity_match_score=0.88,
            liveness_passed=True,
        )
        request = FaceVerificationRequest(
            reference_image=b"ref", probe_image=b"probe",
        )
        result = provider.verify(request)
        assert result.identity_match_score == 0.88
        assert result.liveness_passed is True
        assert result.provider_name == "deterministic"

    def test_deterministic_provider_capabilities(self):
        provider = DeterministicProvider()
        caps = provider.get_capabilities()
        assert caps.supports_identity_match is True
        assert caps.supports_liveness is True


# ─── Anti-Spoofing Failure Non-Fatal ──────────────────────────────────

class TestAntiSpoofingFailureNonFatal:
    """Verify that anti-spoofing failure does not block identity match."""

    def test_anti_spoofing_exception_produces_identity_match(
        self, sample_request: FaceVerificationRequest, mock_uniface
    ):
        mock_uniface["spoofer"].predict.side_effect = RuntimeError("spoof model error")
        from app.services.face_verification.providers.uniface_provider import UniFaceProvider
        provider = UniFaceProvider()

        result = provider.verify(sample_request)

        assert result.identity_match_score is not None
        assert result.liveness_score is None
        assert result.liveness_passed is None
