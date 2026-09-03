"""Tests for face verification provider abstraction (Phase 8.1).

Tests verify:
- Provider interface behavior (protocol conformance)
- Provider failure handling
- No sensitive provider payload leakage
- Correct separation between evidence and decision
- DeterministicProvider correctness
- Factory behavior
- Existing Phase 7 behavior remains intact
"""

import pytest

from app.services.face_verification import (
    DeterministicProvider,
    FaceVerificationError,
    FaceVerificationErrorType,
    FaceVerificationRequest,
    FaceVerificationResult,
    ProviderCapabilities,
    ProviderStatus,
    ProviderUnavailableError,
    get_face_verification_provider,
)
from app.services.face_verification.protocol import FaceVerificationProvider


# ─── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def sample_request() -> FaceVerificationRequest:
    return FaceVerificationRequest(
        reference_image=b"\xff\xd8\xff\xe0fake-jpeg-reference",
        probe_image=b"\xff\xd8\xff\xe0fake-jpeg-probe",
        reference_image_format="image/jpeg",
        probe_image_format="image/jpeg",
        context={"attempt_id": 1, "student_id": 42},
    )


@pytest.fixture
def default_provider() -> DeterministicProvider:
    return DeterministicProvider()


@pytest.fixture
def unavailable_provider() -> DeterministicProvider:
    return DeterministicProvider(available=False)


# ─── Protocol Conformance ───────────────────────────────────────────────

class TestProviderProtocol:
    """Verify that DeterministicProvider satisfies the FaceVerificationProvider protocol."""

    def test_is_protocol_compatible(self, default_provider: DeterministicProvider) -> None:
        assert isinstance(default_provider, FaceVerificationProvider)

    def test_has_verify_method(self, default_provider: DeterministicProvider) -> None:
        assert callable(getattr(default_provider, "verify", None))

    def test_has_health_check_method(self, default_provider: DeterministicProvider) -> None:
        assert callable(getattr(default_provider, "health_check", None))

    def test_has_get_capabilities_method(self, default_provider: DeterministicProvider) -> None:
        assert callable(getattr(default_provider, "get_capabilities", None))


# ─── DeterministicProvider Behavior ─────────────────────────────────────

class TestDeterministicProvider:
    """Verify the deterministic test provider returns correct results."""

    def test_verify_returns_configured_scores(
        self, default_provider: DeterministicProvider, sample_request: FaceVerificationRequest
    ) -> None:
        result = default_provider.verify(sample_request)
        assert isinstance(result, FaceVerificationResult)
        assert result.identity_match_score == 0.92
        assert result.liveness_score == 0.95
        assert result.liveness_passed is True
        assert result.image_quality_score == 0.85

    def test_verify_provider_identity(
        self, default_provider: DeterministicProvider, sample_request: FaceVerificationRequest
    ) -> None:
        result = default_provider.verify(sample_request)
        assert result.provider_name == "deterministic"
        assert result.provider_version == "0.1.0"

    def test_verify_ignores_image_content(
        self, default_provider: DeterministicProvider
    ) -> None:
        req1 = FaceVerificationRequest(reference_image=b"aaa", probe_image=b"bbb")
        req2 = FaceVerificationRequest(reference_image=b"xxx", probe_image=b"yyy")
        r1 = default_provider.verify(req1)
        r2 = default_provider.verify(req2)
        assert r1.identity_match_score == r2.identity_match_score

    def test_verify_custom_scores(self) -> None:
        provider = DeterministicProvider(
            identity_match_score=0.5,
            liveness_score=0.3,
            liveness_passed=False,
            image_quality_score=0.1,
        )
        result = provider.verify(FaceVerificationRequest(
            reference_image=b"r", probe_image=b"p",
        ))
        assert result.identity_match_score == 0.5
        assert result.liveness_passed is False
        assert result.image_quality_score == 0.1

    def test_verify_none_scores(self) -> None:
        provider = DeterministicProvider(
            identity_match_score=None,
            liveness_score=None,
            liveness_passed=None,
            image_quality_score=None,
        )
        result = provider.verify(FaceVerificationRequest(
            reference_image=b"r", probe_image=b"p",
        ))
        assert result.identity_match_score is None
        assert result.liveness_score is None
        assert result.liveness_passed is None
        assert result.image_quality_score is None

    def test_health_check_available(self, default_provider: DeterministicProvider) -> None:
        status = default_provider.health_check()
        assert isinstance(status, ProviderStatus)
        assert status.available is True

    def test_health_check_unavailable(self, unavailable_provider: DeterministicProvider) -> None:
        status = unavailable_provider.health_check()
        assert status.available is False

    def test_capabilities(self, default_provider: DeterministicProvider) -> None:
        caps = default_provider.get_capabilities()
        assert isinstance(caps, ProviderCapabilities)
        assert caps.supports_liveness is True
        assert caps.supports_identity_match is True
        assert caps.supports_image_quality is True
        assert "image/jpeg" in caps.supported_formats


# ─── Provider Failure Handling ──────────────────────────────────────────

class TestProviderFailureHandling:
    """Verify that provider failures are handled correctly."""

    def test_unavailable_provider_raises_error(
        self, unavailable_provider: DeterministicProvider, sample_request: FaceVerificationRequest
    ) -> None:
        with pytest.raises(ProviderUnavailableError) as exc_info:
            unavailable_provider.verify(sample_request)
        assert exc_info.value.error.error_type == FaceVerificationErrorType.PROVIDER_UNAVAILABLE

    def test_provider_error_is_not_decision(self) -> None:
        """Provider errors must NOT be decisions. They are provider-level failures."""
        error = FaceVerificationError(
            error_type=FaceVerificationErrorType.TIMEOUT,
            message="Provider timed out",
        )
        # Error types and decision types are different enums
        from app.models.identity_verification import IdentityVerificationDecision
        for decision in IdentityVerificationDecision:
            assert error.error_type.value != decision.value

    def test_provider_error_has_required_fields(self) -> None:
        error = FaceVerificationError(
            error_type=FaceVerificationErrorType.NO_FACE_DETECTED,
            message="No face found in probe image",
            provider_name="test",
            provider_version="1.0",
            retryable=True,
        )
        assert error.error_type == FaceVerificationErrorType.NO_FACE_DETECTED
        assert error.retryable is True
        assert error.provider_name == "test"


# ─── Sensitive Data Leakage Prevention ──────────────────────────────────

class TestSensitiveDataLeakage:
    """Verify that providers do not leak sensitive data."""

    def test_result_has_no_raw_images(
        self, default_provider: DeterministicProvider, sample_request: FaceVerificationRequest
    ) -> None:
        result = default_provider.verify(sample_request)
        result_dict = vars(result)
        for key, value in result_dict.items():
            if isinstance(value, bytes):
                pytest.fail(f"Result contains raw bytes in field '{key}' — possible image leakage")
            if isinstance(value, str) and len(value) > 1000:
                # Large strings might contain base64-encoded images
                pytest.fail(f"Result contains unusually long string in field '{key}'")

    def test_evidence_metadata_is_safe(
        self, default_provider: DeterministicProvider, sample_request: FaceVerificationRequest
    ) -> None:
        result = default_provider.verify(sample_request)
        metadata = result.evidence_metadata
        assert isinstance(metadata, dict)
        # Metadata should not contain image data
        for key, value in metadata.items():
            assert not isinstance(value, bytes), f"Metadata field '{key}' contains raw bytes"

    def test_error_has_no_image_data(self) -> None:
        error = FaceVerificationError(
            error_type=FaceVerificationErrorType.INVALID_INPUT,
            message="Invalid image format",
        )
        error_dict = vars(error)
        for key, value in error_dict.items():
            assert not isinstance(value, bytes), f"Error field '{key}' contains raw bytes"


# ─── Evidence ≠ Decision Separation ─────────────────────────────────────

class TestEvidenceDecisionSeparation:
    """Verify that provider output is evidence, not a decision."""

    def test_result_has_no_decision_field(
        self, default_provider: DeterministicProvider, sample_request: FaceVerificationRequest
    ) -> None:
        result = default_provider.verify(sample_request)
        result_dict = vars(result)
        decision_fields = {"decision", "authorization", "allow", "deny", "verdict"}
        for field_name in decision_fields:
            assert field_name not in result_dict, (
                f"Result has field '{field_name}' — providers should produce evidence, not decisions"
            )

    def test_result_scores_are_evidence_not_verdicts(
        self, default_provider: DeterministicProvider, sample_request: FaceVerificationRequest
    ) -> None:
        result = default_provider.verify(sample_request)
        # Scores are continuous values [0, 1], not categorical decisions
        if result.identity_match_score is not None:
            assert 0.0 <= result.identity_match_score <= 1.0
        if result.liveness_score is not None:
            assert 0.0 <= result.liveness_score <= 1.0
        if result.image_quality_score is not None:
            assert 0.0 <= result.image_quality_score <= 1.0

    def test_decision_engine_still_works_with_provider_evidence(self) -> None:
        """The existing decision engine must work with evidence from the provider."""
        from app.models.identity_verification import IdentityVerificationEvidence
        from app.services.identity_verification_decision import evaluate_evidence

        # Simulate evidence records produced from provider output
        evidence = IdentityVerificationEvidence(
            attempt_id=1,
            signal_type="similarity_score",
            signal_value="0.92",
            provider_name="deterministic",
            confidence=0.92,
        )
        decision, reasoning = evaluate_evidence([evidence])
        assert decision == "MATCH"
        assert "0.920" in reasoning


# ─── Factory ────────────────────────────────────────────────────────────

class TestFactory:
    """Verify factory creates correct provider from config."""

    def test_get_provider_returns_protocol(self) -> None:
        provider = get_face_verification_provider()
        assert isinstance(provider, FaceVerificationProvider)

    def test_get_provider_returns_deterministic_by_default(self) -> None:
        provider = get_face_verification_provider()
        assert isinstance(provider, DeterministicProvider)


# ─── Request/Response Immutability ──────────────────────────────────────

class TestImmutability:
    """Verify dataclass frozen status prevents accidental mutation."""

    def test_request_is_frozen(self) -> None:
        req = FaceVerificationRequest(reference_image=b"r", probe_image=b"p")
        with pytest.raises(AttributeError):
            req.reference_image = b"modified"  # type: ignore[misc]

    def test_result_is_frozen(self) -> None:
        result = FaceVerificationResult(provider_name="test")
        with pytest.raises(AttributeError):
            result.provider_name = "modified"  # type: ignore[misc]

    def test_error_is_frozen(self) -> None:
        error = FaceVerificationError(
            error_type=FaceVerificationErrorType.TIMEOUT,
            message="timeout",
        )
        with pytest.raises(AttributeError):
            error.message = "modified"  # type: ignore[misc]

    def test_capabilities_is_frozen(self) -> None:
        caps = ProviderCapabilities(provider_name="test")
        with pytest.raises(AttributeError):
            caps.provider_name = "modified"  # type: ignore[misc]

    def test_status_is_frozen(self) -> None:
        status = ProviderStatus(provider_name="test")
        with pytest.raises(AttributeError):
            status.provider_name = "modified"  # type: ignore[misc]
