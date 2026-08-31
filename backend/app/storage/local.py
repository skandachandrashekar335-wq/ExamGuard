import os
import uuid
from pathlib import Path

from app.storage.base import StorageBackend


class LocalStorage(StorageBackend):
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, data: bytes) -> str:
        dest = self.base_dir / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return key

    def get_path(self, key: str) -> str:
        resolved = (self.base_dir / key).resolve()
        if not str(resolved).startswith(str(self.base_dir.resolve())):
            raise FileNotFoundError("Path traversal detected")
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {key}")
        return str(resolved)

    def delete(self, key: str) -> None:
        target = (self.base_dir / key).resolve()
        if not str(target).startswith(str(self.base_dir.resolve())):
            raise FileNotFoundError("Path traversal detected")
        if not target.exists():
            raise FileNotFoundError(f"File not found: {key}")
        target.unlink()

    @staticmethod
    def generate_key(original_filename: str) -> str:
        ext = Path(original_filename).suffix.lower()
        unique_id = uuid.uuid4().hex
        return f"documents/{unique_id}{ext}"
