import io
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document, DocumentStatus, DocumentType
from app.storage.local import LocalStorage

settings = get_settings()

MAGIC_BYTES = {
    b"\x25\x50\x44\x46": "application/pdf",
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89\x50\x4e\x47": "image/png",
}

EXTENSION_MAP = {
    ".pdf": ("application/pdf", "PDF"),
    ".jpg": ("image/jpeg", "JPEG"),
    ".jpeg": ("image/jpeg", "JPEG"),
    ".png": ("image/png", "PNG"),
}


def detect_content_type(data: bytes) -> str | None:
    for magic, mime in MAGIC_BYTES.items():
        if data[:4].startswith(magic):
            return mime
    return None


def validate_upload(
    filename: str,
    content_type: str,
    data: bytes,
    doc_type: str,
) -> tuple[bool, str]:
    if len(data) == 0:
        return False, "File is empty"

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(data) > max_bytes:
        return False, f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB"

    if doc_type not in settings.ALLOWED_DOCUMENT_TYPES:
        return False, f"Document type '{doc_type}' is not allowed"

    ext = Path(filename).suffix.lower()
    if ext not in EXTENSION_MAP:
        return False, f"File extension '{ext}' is not supported"

    detected = detect_content_type(data)
    if detected is None:
        return False, "Unrecognized file format"

    expected_mime, _ = EXTENSION_MAP[ext]
    if detected != expected_mime:
        return False, f"File content does not match extension '{ext}'"

    return True, "OK"


def upload_document(
    db: Session,
    filename: str,
    content_type: str,
    data: bytes,
    doc_type: str,
) -> Document:
    ok, message = validate_upload(filename, content_type, data, doc_type)
    if not ok:
        raise ValueError(message)

    storage = LocalStorage(settings.UPLOAD_DIR)
    key = LocalStorage.generate_key(filename)
    storage.save(key, data)

    document = Document(
        original_filename=filename,
        stored_key=key,
        content_type=content_type,
        file_size=len(data),
        document_type=DocumentType(doc_type),
        status=DocumentStatus.READY_FOR_PROCESSING,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def get_document(db: Session, document_id: int) -> Document | None:
    return db.query(Document).filter(Document.id == document_id).first()


def list_documents(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    doc_type: str | None = None,
) -> tuple[list[Document], int]:
    query = db.query(Document)

    if doc_type:
        query = query.filter(Document.document_type == doc_type)

    total = query.count()
    documents = (
        query.order_by(Document.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return documents, total
