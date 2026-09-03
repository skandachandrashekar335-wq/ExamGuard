"""Protocol defining the face verification provider interface.

Any face verification provider (UniFace, self-hosted, institutional,
deterministic/mock) must implement this protocol.

The protocol is intentionally minimal. Providers produce evidence.
ExamGuard's decision engine evaluates that evidence.

AI/perception = evidence.
Business logic = authority.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.services.face_verification.types import (
    FaceVerificationRequest,
    FaceVerificationResult,
    ProviderCapabilities,
    ProviderStatus,
)


@runtime_checkable
class FaceVerificationProvider(Protocol):
    """Protocol for face verification providers.

    Implementations must:
    - Return evidence signals (scores, liveness, quality)
    - NOT make authorization decisions
    - NOT log raw images or biometric templates
    - NOT expose provider credentials in responses
    - Handle errors gracefully with typed error information

    The provider is a PERCEPTION layer. It produces evidence
    that the decision engine evaluates. It never directly
    authorizes or denies exam entry.
    """

    def verify(self, request: FaceVerificationRequest) -> FaceVerificationResult:
        """Verify a probe image against a reference image.

        Args:
            request: Contains reference and probe image bytes,
                     formats, and optional context.

        Returns:
            FaceVerificationResult with evidence signals.
            Scores are in [0.0, 1.0] range where applicable.
            None values indicate the signal was not produced.
        """
        ...

    def health_check(self) -> ProviderStatus:
        """Check if the provider is available and healthy.

        Returns:
            ProviderStatus indicating availability.
        """
        ...

    def get_capabilities(self) -> ProviderCapabilities:
        """Describe provider capabilities.

        Returns:
            ProviderCapabilities describing what this provider supports.
        """
        ...
