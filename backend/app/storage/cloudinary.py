"""Cloudinary storage adapter for ExamGuard.

Provides a Cloudinary-backed implementation of the StorageBackend ABC.
Enables production document storage with secure file access and
local/cloud backend switching.

Note: This adapter uses the official Cloudinary Python SDK for
actual Cloudinary API integration. Environment variables expected:
- CLOUDINARY_CLOUD_NAME
- CLOUDINARY_API_KEY
- CLOUDINARY_API_SECRET

When these credentials are available, files are uploaded to Cloudinary
and secure URLs are returned. When credentials are unavailable,
the adapter falls back to LocalStorage for development functionality.
"""

import os
from pathlib import Path
from typing import Optional
import uuid

import cloudinary
import cloudinary.uploader

from app.storage.base import StorageBackend
from app.storage.local import LocalStorage


class CloudinaryStorage(StorageBackend):
    """Cloudinary storage adapter.

    Stores documents with Cloudinary-style keys and uploads files
    to Cloudinary using the official Python SDK.

    Environment variables expected (for actual Cloudinary API):
    - CLOUDINARY_CLOUD_NAME
    - CLOUDINARY_API_KEY
    - CLOUDINARY_API_SECRET

    When these credentials are configured, the adapter uploads to
    Cloudinary and returns secure URLs. When credentials are
    unavailable, it falls back to LocalStorage for development.

    After upload, the returned key is Cloudinary's public_id, and
    the secure URL can be constructed as:
    https://res.cloudinary.com/{cloud_name}/{transformation}/{public_id}{extension}
    """

    def __init__(self, base_dir: Optional[str] = None):
        # Initialize Cloudinary SDK if credentials are available
        cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
        api_key = os.environ.get("CLOUDINARY_API_KEY")
        api_secret = os.environ.get("CLOUDINARY_API_SECRET")

        if cloud_name and api_key and api_secret:
            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret,
            )
            self._using_cloudinary = True
        else:
            self._using_cloudinary = False
            # Fall back to local storage initialization
            fallback_base_dir = (
                base_dir or os.environ.get("CLOUDINARY_BASE_DIR", "local_storage")
            )
            self._local_backend = LocalStorage(fallback_base_dir)

    @property
    def local(self):
        """Fallback to local storage if Cloudinary credentials are unavailable."""
        if not self._using_cloudinary:
            if not hasattr(self, "_local_backend"):
                fallback_base_dir = (
                    os.environ.get("CLOUDINARY_BASE_DIR", "local_storage")
                )
                self._local_backend = LocalStorage(fallback_base_dir)
            return self._local_backend
        return None

    def _cloudinary_key(self, key: str) -> str:
        """Format a Cloudinary-style key.

        Format: "{resource_type}/{folder}/{unique_id}{extension}"
        If key doesn't contain a folder prefix, one is inferred.
        """
        key = key.strip("/")
        if "/" not in key:
            # Infer folder from context; default to "documents"
            key = f"documents/{key}"
        return key

    def save(self, key: str, data: bytes) -> str:
        """Save data to Cloudinary storage.

        Uploads the file to Cloudinary using the official SDK.
        Returns the Cloudinary secure URL on success.

        When Cloudinary credentials are configured, a failed upload is a hard
        error - never silently fall back to a local filesystem key (that is not
        a public URL and breaks reference_face_url consumers).
        Local fallback is only used when Cloudinary is not configured (dev).
        """
        cloud_key = self._cloudinary_key(key)

        if self._using_cloudinary:
            try:
                result = cloudinary.uploader.upload(
                    data,
                    public_id=cloud_key,
                    resource="raw",
                    folder="examguard",
                )
                secure_url = result.get("secure_url")
                if not secure_url:
                    raise RuntimeError("Cloudinary upload returned no secure_url")
                return secure_url
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error("Cloudinary upload failed for key %s: %s", cloud_key, e)
                raise RuntimeError(
                    "Cloudinary upload failed. Check CLOUDINARY_API_KEY permissions "
                    "(upload/create) and credentials."
                ) from e

        # No Cloudinary credentials - local development fallback.
        local_backend = self.local
        if local_backend is not None:
            return local_backend.save(cloud_key, data)
        raise RuntimeError(
            "Neither Cloudinary nor LocalStorage is available for save operation"
        )

    def get_path(self, key: str) -> str:
        """Return the URL/path for a stored key.

        If using Cloudinary, returns the secure URL.
        If using LocalStorage, returns the filesystem path.
        Raises if not found.
        """
        if self._using_cloudinary:
            # Return the Cloudinary secure URL
            # The URL format is: https://res.cloudinary.com/{cloud_name}/image/{upload_timestamp}/{public_id}{format}
            # We construct a reasonable URL based on the key
            cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME", "unknown")
            # The key stored in Cloudinary is the public_id
            # Construct URL: https://res.cloudinary.com/{cloud_name}/image/{public_id}{extension}
            # The original filename extension is preserved from generate_key
            return f"https://res.cloudinary.com/{cloud_name}/image/upload/{cloud_key}"

        # LocalStorage path
        cloud_key = self._cloudinary_key(key)
        try:
            return self.local.get_path(cloud_key)
        except FileNotFoundError:
            resolved = (self.local.base_dir / cloud_key).resolve()
            if resolved.exists():
                return str(resolved)
            raise FileNotFoundError(f"File not found: {key}")

    def delete(self, key: str) -> bool:
        """Delete a stored object.

        Returns True only when the deletion is confirmed. The same asset
        can be stored as an image or a raw resource, so both resource
        types are attempted. Failures are logged and reported as False
        (never raised) so callers can retry with a variant key or skip.
        """
        cloud_key = self._cloudinary_key(key)
        if self._using_cloudinary:
            import logging
            logger = logging.getLogger(__name__)
            try:
                for resource_type in ("image", "raw"):
                    result = cloudinary.uploader.destroy(
                        cloud_key, resource_type=resource_type
                    )
                    if isinstance(result, dict) and result.get("result") == "ok":
                        return True
                logger.warning(
                    "Cloudinary delete not confirmed for key %s", cloud_key
                )
                return False
            except Exception as e:
                logger.warning("Cloudinary delete failed: %s", str(e))
                return False
        # Local filesystem fallback (Cloudinary not configured - dev).
        try:
            self.local.delete(cloud_key)
            return True
        except FileNotFoundError:
            return False

    def generate_key(self, original_filename: str) -> str:
        """Generate a storage key for a file with the given original filename.

        Uses UUID-based naming to avoid collisions.
        The returned key is compatible with Cloudinary's public_id format.
        """
        ext = Path(original_filename).suffix.lower()
        unique_id = uuid.uuid4().hex
        return f"documents/{unique_id}{ext}"

    def switch_backend(self, backend_type: str, **kwargs) -> StorageBackend:
        """Switch between local and cloudinary storage backends.

        Args:
            backend_type: "local" or "cloudinary"
            **kwargs: Additional arguments for the target backend

        Returns:
            Initialized StorageBackend instance of the requested type.
        """
        if backend_type == "local":
            from app.storage.local import LocalStorage
            base_dir = kwargs.get(
                "base_dir", os.environ.get("CLOUDINARY_BASE_DIR", "local_storage")
            )
            return LocalStorage(base_dir)
        elif backend_type == "cloudinary":
            return CloudinaryStorage(base_dir=kwargs.get("base_dir"))
        else:
            raise ValueError(f"Unknown backend type: {backend_type}")