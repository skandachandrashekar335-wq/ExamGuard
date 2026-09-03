"""UniFace face verification provider.

Integrates yakhyo/uniface (v4.0.0) for real face detection, recognition,
and anti-spoofing. Maps UniFace outputs into ExamGuard's evidence domain.

UniFace performs all processing locally via ONNX Runtime.
No external API calls are made during inference.
Models are downloaded on first use and cached at ~/.uniface/models/.

Architecture:
    UniFaceFaceVerificationProvider
        ↓
    UniFace (RetinaFace detection + ArcFace recognition + MiniFASNet anti-spoofing)
        ↓
    FaceVerificationResult (evidence signals)
        ↓
    ExamGuard decision engine (evaluate_evidence)

Privacy:
    - Raw face images are never logged or stored
    - Biometric embeddings are used transiently only
    - No embeddings appear in evidence metadata
    - Provider internals remain private
"""

from __future__ import annotations

import io
import logging
from typing import Any

import cv2
import numpy as np

from app.core.config import get_settings
from app.services.face_verification.providers.deterministic import (
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

logger = logging.getLogger(__name__)

UNIFACE_VERSION = "4.0.0"


def _bytes_to_cv_image(image_bytes: bytes) -> np.ndarray:
    """Decode image bytes to OpenCV BGR numpy array.

    Args:
        image_bytes: Raw image file bytes (JPEG, PNG, etc.)

    Returns:
        numpy array in BGR format (OpenCV convention)

    Raises:
        ValueError: If image bytes cannot be decoded
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode image bytes")
    return image


class UniFaceProvider:
    """Face verification provider using UniFace library.

    Uses RetinaFace for detection, ArcFace for recognition,
    and MiniFASNet for anti-spoofing. All processing is local
    via ONNX Runtime — no external API calls.

    Models are lazily initialized on first verify() call.
    Downloads happen automatically on first use (~30 MB total).
    """

    PROVIDER_NAME = "uniface"
    PROVIDER_VERSION = UNIFACE_VERSION

    def __init__(
        self,
        *,
        detection_model: str = "retinaface",
        recognition_model: str = "arcface",
        anti_spoofing: bool = True,
    ) -> None:
        """Initialize the UniFace provider.

        Args:
            detection_model: Face detection model name.
            recognition_model: Face recognition model name.
            anti_spoofing: Whether to enable anti-spoofing checks.
        """
        self._detection_model = detection_model
        self._recognition_model = recognition_model
        self._anti_spoofing_enabled = anti_spoofing

        # Lazy-initialized UniFace components (set during _ensure_initialized)
        self._detector: Any = None
        self._recognizer: Any = None
        self._spoofer: Any = None
        self._initialized = False
        self._init_error: str | None = None

    def _load_uniface_modules(self) -> tuple[Any, Any, Any | None]:
        """Load UniFace modules. Separated for testability.

        Returns:
            Tuple of (detector_class, recognizer_class, spoofer_class_or_None)

        Raises:
            ImportError: If uniface is not installed.
        """
        from uniface.detection import RetinaFace
        from uniface.recognition import ArcFace

        spoofer_class = None
        if self._anti_spoofing_enabled:
            from uniface.spoofing import MiniFASNet
            spoofer_class = MiniFASNet

        return RetinaFace, ArcFace, spoofer_class

    def _ensure_initialized(self) -> None:
        """Lazily initialize UniFace models.

        Downloads models on first use if not cached.
        """
        if self._initialized:
            return
        if self._init_error is not None:
            raise ProviderUnavailableError(
                FaceVerificationError(
                    error_type=FaceVerificationErrorType.PROVIDER_UNAVAILABLE,
                    message=f"UniFace initialization failed: {self._init_error}",
                    provider_name=self.PROVIDER_NAME,
                    provider_version=self.PROVIDER_VERSION,
                )
            )

        try:
            RetinaFace, ArcFace, MiniFASNet = self._load_uniface_modules()

            self._detector = RetinaFace()
            self._recognizer = ArcFace()

            if MiniFASNet is not None:
                self._spoofer = MiniFASNet()

            self._initialized = True
            logger.info(
                "UniFace provider initialized: detection=%s, recognition=%s, anti_spoofing=%s",
                self._detection_model,
                self._recognition_model,
                self._anti_spoofing_enabled,
            )
        except Exception as e:
            self._init_error = str(e)
            logger.error("UniFace initialization failed: %s", e)
            raise ProviderUnavailableError(
                FaceVerificationError(
                    error_type=FaceVerificationErrorType.PROVIDER_UNAVAILABLE,
                    message=f"Failed to initialize UniFace: {e}",
                    provider_name=self.PROVIDER_NAME,
                    provider_version=self.PROVIDER_VERSION,
                )
            ) from e

    def verify(self, request: FaceVerificationRequest) -> FaceVerificationResult:
        """Verify a probe image against a reference image using UniFace.

        Pipeline:
        1. Decode both images
        2. Detect faces in reference image (must be exactly 1)
        3. Detect faces in probe image (must be exactly 1)
        4. Extract embeddings via ArcFace
        5. Compute cosine similarity → identity_match_score
        6. Run MiniFASNet anti-spoofing on probe → liveness evidence
        7. Return evidence signals (NOT a decision)

        Args:
            request: Reference and probe image bytes.

        Returns:
            FaceVerificationResult with evidence signals.

        Raises:
            ProviderUnavailableError: If provider cannot produce evidence.
        """
        self._ensure_initialized()

        try:
            ref_image = _bytes_to_cv_image(request.reference_image)
            probe_image = _bytes_to_cv_image(request.probe_image)
        except ValueError as e:
            raise ProviderUnavailableError(
                FaceVerificationError(
                    error_type=FaceVerificationErrorType.INVALID_INPUT,
                    message=f"Invalid image: {e}",
                    provider_name=self.PROVIDER_NAME,
                    provider_version=self.PROVIDER_VERSION,
                )
            ) from e

        # Detect faces in reference image
        ref_faces = self._detector.detect(ref_image)
        if not ref_faces:
            raise ProviderUnavailableError(
                FaceVerificationError(
                    error_type=FaceVerificationErrorType.NO_FACE_DETECTED,
                    message="No face detected in reference image",
                    provider_name=self.PROVIDER_NAME,
                    provider_version=self.PROVIDER_VERSION,
                )
            )
        if len(ref_faces) > 1:
            raise ProviderUnavailableError(
                FaceVerificationError(
                    error_type=FaceVerificationErrorType.MULTIPLE_FACES_DETECTED,
                    message=f"Multiple faces ({len(ref_faces)}) detected in reference image",
                    provider_name=self.PROVIDER_NAME,
                    provider_version=self.PROVIDER_VERSION,
                )
            )

        # Detect faces in probe image
        probe_faces = self._detector.detect(probe_image)
        if not probe_faces:
            raise ProviderUnavailableError(
                FaceVerificationError(
                    error_type=FaceVerificationErrorType.NO_FACE_DETECTED,
                    message="No face detected in probe image",
                    provider_name=self.PROVIDER_NAME,
                    provider_version=self.PROVIDER_VERSION,
                )
            )
        if len(probe_faces) > 1:
            raise ProviderUnavailableError(
                FaceVerificationError(
                    error_type=FaceVerificationErrorType.MULTIPLE_FACES_DETECTED,
                    message=f"Multiple faces ({len(probe_faces)}) detected in probe image",
                    provider_name=self.PROVIDER_NAME,
                    provider_version=self.PROVIDER_VERSION,
                )
            )

        # Extract embeddings
        try:
            ref_embedding = self._recognizer.get_normalized_embedding(
                ref_image, ref_faces[0].landmarks
            )
            probe_embedding = self._recognizer.get_normalized_embedding(
                probe_image, probe_faces[0].landmarks
            )
        except Exception as e:
            raise ProviderUnavailableError(
                FaceVerificationError(
                    error_type=FaceVerificationErrorType.IDENTITY_MATCH_UNAVAILABLE,
                    message=f"Embedding extraction failed: {e}",
                    provider_name=self.PROVIDER_NAME,
                    provider_version=self.PROVIDER_VERSION,
                )
            ) from e

        # Compute cosine similarity (embeddings are L2-normalized)
        identity_match_score = float(np.dot(ref_embedding, probe_embedding))

        # Anti-spoofing on probe image
        liveness_score: float | None = None
        liveness_passed: bool | None = None
        if self._spoofer is not None:
            try:
                spoof_result = self._spoofer.predict(probe_image, probe_faces[0].bbox)
                liveness_score = float(spoof_result.confidence)
                liveness_passed = bool(spoof_result.is_real)
            except Exception as e:
                # Anti-spoofing failure is non-fatal — identity match still valid
                logger.warning("Anti-spoofing failed: %s", e)

        return FaceVerificationResult(
            identity_match_score=identity_match_score,
            liveness_score=liveness_score,
            liveness_passed=liveness_passed,
            image_quality_score=None,
            provider_name=self.PROVIDER_NAME,
            provider_version=self.PROVIDER_VERSION,
            evidence_metadata={
                "source": "uniface_provider",
                "detection_model": self._detection_model,
                "recognition_model": self._recognition_model,
                "anti_spoofing_enabled": self._anti_spoofing_enabled,
            },
        )

    def health_check(self) -> ProviderStatus:
        """Check if UniFace is available and models can be loaded.

        Returns:
            ProviderStatus indicating availability.
        """
        try:
            self._ensure_initialized()
            return ProviderStatus(
                available=True,
                message="UniFace provider ready",
                provider_name=self.PROVIDER_NAME,
                provider_version=self.PROVIDER_VERSION,
            )
        except ProviderUnavailableError as e:
            return ProviderStatus(
                available=False,
                message=e.error.message,
                provider_name=self.PROVIDER_NAME,
                provider_version=self.PROVIDER_VERSION,
            )

    def get_capabilities(self) -> ProviderCapabilities:
        """Describe UniFace provider capabilities.

        Returns:
            ProviderCapabilities for UniFace.
        """
        return ProviderCapabilities(
            supports_liveness=self._anti_spoofing_enabled,
            supports_identity_match=True,
            supports_image_quality=False,
            max_image_size_bytes=get_settings().FACE_VERIFICATION_MAX_IMAGE_SIZE_MB * 1024 * 1024,
            supported_formats=("image/jpeg", "image/png"),
            provider_name=self.PROVIDER_NAME,
            provider_version=self.PROVIDER_VERSION,
        )
