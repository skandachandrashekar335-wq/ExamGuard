"""Deterministic face verification provider for testing.

This provider returns configurable results without any external
calls. It is used for:
- Unit testing the provider abstraction
- Integration testing the evidence pipeline
- Development without a real provider

This provider does NOT:
- Call any external API
- Process actual images
- Store any data
- Perform real face recognition
"""

from __future__ import annotations

from app.services.face_verification.types import (
    FaceVerificationRequest,
    FaceVerificationResult,
    ProviderCapabilities,
    ProviderStatus,
)


class DeterministicProvider:
    """A test provider that returns pre-configured results.

    Usage:
        provider = DeterministicProvider(
            identity_match_score=0.92,
            liveness_passed=True,
            image_quality_score=0.85,
        )
        result = provider.verify(request)
        # result.identity_match_score == 0.92
    """

    PROVIDER_NAME = "deterministic"
    PROVIDER_VERSION = "0.1.0"

    def __init__(
        self,
        *,
        identity_match_score: float | None = 0.92,
        liveness_score: float | None = 0.95,
        liveness_passed: bool | None = True,
        image_quality_score: float | None = 0.85,
        available: bool = True,
    ) -> None:
        self._identity_match_score = identity_match_score
        self._liveness_score = liveness_score
        self._liveness_passed = liveness_passed
        self._image_quality_score = image_quality_score
        self._available = available

    def verify(self, request: FaceVerificationRequest) -> FaceVerificationResult:
        """Return pre-configured evidence signals.

        Ignores the actual image content. Returns the scores
        configured at construction time.
        """
        if not self._available:
            from app.services.face_verification.types import (
                FaceVerificationError,
                FaceVerificationErrorType,
            )
            raise ProviderUnavailableError(
                FaceVerificationError(
                    error_type=FaceVerificationErrorType.PROVIDER_UNAVAILABLE,
                    message="DeterministicProvider is configured as unavailable",
                    provider_name=self.PROVIDER_NAME,
                    provider_version=self.PROVIDER_VERSION,
                )
            )

        return FaceVerificationResult(
            identity_match_score=self._identity_match_score,
            liveness_score=self._liveness_score,
            liveness_passed=self._liveness_passed,
            image_quality_score=self._image_quality_score,
            provider_name=self.PROVIDER_NAME,
            provider_version=self.PROVIDER_VERSION,
            evidence_metadata={"source": "deterministic_test"},
        )

    def health_check(self) -> ProviderStatus:
        """Return configured availability status."""
        return ProviderStatus(
            available=self._available,
            message="OK" if self._available else "Configured as unavailable",
            provider_name=self.PROVIDER_NAME,
            provider_version=self.PROVIDER_VERSION,
        )

    def get_capabilities(self) -> ProviderCapabilities:
        """Return deterministic capabilities."""
        return ProviderCapabilities(
            supports_liveness=True,
            supports_identity_match=True,
            supports_image_quality=True,
            max_image_size_bytes=None,
            supported_formats=("image/jpeg", "image/png"),
            provider_name=self.PROVIDER_NAME,
            provider_version=self.PROVIDER_VERSION,
        )


class ProviderUnavailableError(Exception):
    """Raised when a provider is not available.

    Wraps a FaceVerificationError for typed error handling.
    """

    def __init__(self, error: FaceVerificationError) -> None:
        self.error = error
        super().__init__(error.message)
