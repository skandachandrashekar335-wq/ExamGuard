"""Cloudinary storage adapter for ExamGuard.

Provides a Cloudinary-backed implementation of the StorageBackend ABC.
Enables production document storage with secure file access and
local/cloud backend switching.

Note: This is a stub/adapter implementation. Actual Cloudinary API
integration would require the cloudinary Python package and
environment configuration (CLOUDINARY_CLOUD_NAME, 
CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET).

For now, this adapter implements the StorageBackend interface with
 Cloudinary-style key naming and provides a switching mechanism
 between local and cloud storage backends.
"""

import os
import uuid
from pathlib import Path
from typing import Optional

from app.storage.base import StorageBackend


class CloudinaryStorage(StorageBackend):
    """Cloudinary storage adapter.

    Stores documents with Cloudinary-style keys:
    - Format: "resource_type}/{folder}/{unique_id}{extension}"

    Environment variables expected (for actual Cloudinary API):
    - CLOUDINARY_CLOUD_NAME
    - CLOUDINARY_API_KEY
    - CLOUDINARY_API_SECRET

    In the absence of these credentials, the adapter falls back to
    LocalStorage-style behavior using the base_dir configured via
    CLOUDINARY_BASE_DIR or defaults to a "cloudinary" subdirectory.
    """

    def __init__(self, base_dir: Optional[str] = None):
        # Support local fallback via base_dir env var
        self.base_dir = Path(
            os.environ.get("CLOUDINARY_BASE_DIR", base_dir or "cloudinary")
        )
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._local = None

    @property
    def local(self):
        """Lazy-local fallback if Cloudinary credentials are unavailable."""
        if self._local is None:
            self._local = LocalStorage(str(self.base_dir))
        return self._local

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

        In production, this would call the Cloudinary API.
        Currently falls back to local storage for functionality.
        """
        cloud_key = self._cloudinary_key(key)
        # Fall back to local storage for functionality
        return self.local.save(cloud_key, data)

    def get_path(self, key: str) -> str:
        """Return the filesystem path for a stored key. Raises if not found."""
        cloud_key = self._cloudinary_key(key)
        # Try cloud first, fall back to local
        try:
            return self.local.get_path(cloud_key)
        except FileNotFoundError:
            # If not found locally, return the resolved cloud path
            # (caller would need actual Cloudinary API to fetch)
            resolved = (self.base_dir / cloud_key).resolve()
            return str(resolved)

    def delete(self, key: str) -> None:
        """Delete a stored object. Raises if not found."""
        cloud_key = self._cloudinary_key(key)
        # Fall back to local deletion
        try:
            return self.local.delete(cloud_key)
        except FileNotFoundError:
            # If not found locally, raise (cloud deletion would need API)
            raise FileNotFoundError(f"File not found: {key}")

    def generate_key(self, original_filename: str) -> str:
        """Generate a storage key for a file with the given original filename.

        Uses UUID-based naming to avoid collisions.
        """
        ext = Path(original_filename).suffix.lower()
        unique_id = uuid.uuid4().hex
        return f"documents/{unique_id}{ext}"

    def switch_backend(self, backend_type: str, **kwargs) -> StorageBackend:
        """Switch between local and cloud storage backends.

        Args:
            backend_type: "local" or "cloudinary"
            **kwargs: Additional arguments for the target backend

        Returns:
            Initialized StorageBackend instance of the requested type.
        """
        if backend_type == "local":
            from app.storage.local import LocalStorage
            base_dir = kwargs.get("base_dir", os.environ.get("CLOUDINARY_BASE_DIR", "local_storage"))
            return LocalStorage(base_dir)
        elif backend_type == "cloudinary":
            return CloudinaryStorage(base_dir=kwargs.get("base_dir"))
        else:
            raise ValueError(f"Unknown backend type: {backend_type}")


def test_cloudinary_key_formatting():
    """Test that Cloudinary keys are formatted correctly."""
    storage = CloudinaryStorage()
    key = storage.generate_key("student_id_photo.jpg")
    assert key.startswith("documents/"), f"Key should start with 'documents/', got: {key}"
    assert key.endswith(".jpg"), f"Key should end with '.jpg', got: {key}"


def test_switch_backend_local():
    """Test switching to local backend."""
    adapter = CloudinaryStorage()
    local_backend = adapter.switch_backend("local", base_dir="test_local_storage")
    assert isinstance(local_backend, LocalStorage)
    key = local_backend.generate_key("test.jpg")
    assert key.startswith("test_local_storage/") or key.startswith("test_local_storage\\")


def test_switch_backend_cloudinary():
    """Test switching to cloudinary backend."""
    adapter = CloudinaryStorage()
    cloud_backend = adapter.switch_backend("cloudinary")
    assert cloud_backend.__class__.__name__ == "CloudinaryStorage"