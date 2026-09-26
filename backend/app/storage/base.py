from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes) -> str:
        """Save data to storage, return the storage key."""

    @abstractmethod
    def get_path(self, key: str) -> str:
        """Return the filesystem path for a stored key. Raises if not found."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a stored object. Return True when deletion is confirmed."""
