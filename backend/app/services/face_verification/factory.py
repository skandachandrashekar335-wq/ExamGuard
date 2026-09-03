"""Factory for creating face verification providers.

The factory reads configuration and returns the appropriate provider
implementation. This keeps business logic decoupled from specific
provider implementations.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.services.face_verification.protocol import FaceVerificationProvider
from app.services.face_verification.providers.deterministic import (
    DeterministicProvider,
)


def get_face_verification_provider() -> FaceVerificationProvider:
    """Create and return the configured face verification provider.

    Reads FACE_VERIFICATION_PROVIDER from settings to determine
    which provider implementation to instantiate.

    Returns:
        A FaceVerificationProvider instance.

    Raises:
        ValueError: If the configured provider name is not recognized.
    """
    settings = get_settings()
    provider_name = settings.FACE_VERIFICATION_PROVIDER.lower()

    if provider_name == "deterministic":
        return DeterministicProvider()

    if provider_name == "none" or provider_name == "":
        return DeterministicProvider(available=False)

    # Future providers will be added here:
    # elif provider_name == "uniface":
    #     from app.services.face_verification.providers.uniface import UnifaceProvider
    #     return UnifaceProvider(...)

    raise ValueError(
        f"Unknown face verification provider: {provider_name!r}. "
        f"Configured providers: deterministic, none"
    )
