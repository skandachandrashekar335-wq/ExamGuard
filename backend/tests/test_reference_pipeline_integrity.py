"""Reference-face pipeline integrity (Problem B root-cause regression tests).

Covers the two bugs that made "Replace Reference Face" a no-op and let a
stale face produce a genuine 0.404 NO_MATCH:

1. CloudinaryStorage.save() used a deterministic public_id with the SDK's
   default overwrite=False — new bytes were silently discarded and the
   existing asset returned. Re-uploads must overwrite + invalidate CDN.
2. The URL-keyed in-process cache (_reference_cache, 120s TTL) kept serving
   the OLD reference bytes after a re-upload that returned the same URL —
   verify-face compared the probe against a stale face. Upload paths must
   invalidate the cache.
"""

import base64
import time
from datetime import date, time as dtime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest
from sqlalchemy import delete

from app.auth import Role, get_current_user
from app.core.database import SessionLocal
from app.main import app
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.identity_verification import IdentityVerificationAttempt
from app.models.student import Student
from app.models.subject import Subject
from app.storage.cloudinary import CloudinaryStorage

REFERENCE_FACE_URL = "/api/v1/identity-verifications/{attempt_id}/reference-face"
STABLE_URL = (
    "https://res.cloudinary.com/test-cloud/raw/upload/"
    "examguard/face-references/attempt-stable.png"
)


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def cleanup():
    """Remove PPI-prefixed test data and stale cache entries."""
    from app.api.v1 import identity_verification as iv_api

    db = SessionLocal()
    try:
        student_ids = db.query(Student.id).filter(Student.usn.ilike("PPI%"))
        reg_ids = db.query(ExamRegistration.id).filter(
            ExamRegistration.student_id.in_(student_ids)
        )
        attempt_ids = db.query(IdentityVerificationAttempt.id).filter(
            IdentityVerificationAttempt.exam_registration_id.in_(reg_ids)
        )
        db.execute(delete(IdentityVerificationAttempt).where(
            IdentityVerificationAttempt.id.in_(attempt_ids)
        ))
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.id.in_(reg_ids)
        ))
        exam_ids = db.query(Exam.id).filter(Exam.exam_name.ilike("PPI%"))
        db.execute(delete(Exam).where(Exam.id.in_(exam_ids)))
        db.execute(delete(ExamHall).where(ExamHall.building.ilike("PPI%")))
        db.execute(delete(Subject).where(Subject.code.ilike("PPI%")))
        db.execute(delete(Student).where(Student.usn.ilike("PPI%")))
        db.commit()
    finally:
        db.close()
    iv_api.invalidate_reference_cache()
    yield
    iv_api.invalidate_reference_cache()


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()


def _set_cloudinary_env(monkeypatch):
    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "test-cloud")
    monkeypatch.setenv("CLOUDINARY_API_KEY", "test-key")
    monkeypatch.setenv("CLOUDINARY_API_SECRET", "test-secret")


def _mk_attempt(db):
    subject = Subject(
        code="PPI001", name="PPI Subject", department="PPI Dept",
        semester=6, credits=3,
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)

    exam = Exam(
        subject_id=subject.id, exam_name="PPI Exam",
        exam_date=date(2026, 12, 4), start_time=dtime(9, 0),
        end_time=dtime(12, 0), semester=6, department="PPI Dept",
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    hall = ExamHall(building="PPI Hall", room_number="101", capacity=50)
    db.add(hall)
    db.commit()
    db.refresh(hall)

    student = Student(usn="PPI001", name="PPI Student")
    db.add(student)
    db.commit()
    db.refresh(student)

    reg = ExamRegistration(
        student_id=student.id, exam_id=exam.id,
        status=RegistrationStatus.REGISTERED.value,
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)

    attempt = IdentityVerificationAttempt(
        student_id=student.id, exam_registration_id=reg.id,
        status="CREATED", decision="PENDING",
        verification_method="FACE",
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return SimpleNamespace(student=student, reg=reg, attempt=attempt)


def _png_b64(size=32):
    image = np.full((size, size, 3), 32, np.uint8)
    ok, buf = cv2.imencode(".png", image)
    assert ok
    return base64.b64encode(buf.tobytes()).decode()


def _seed_cache(url, payload=b"OLD-REFERENCE-BYTES"):
    from app.api.v1 import identity_verification as iv_api

    with iv_api._reference_cache_lock:
        iv_api._reference_cache[url] = (time.time(), payload)


def _cached_bytes(url):
    from app.api.v1 import identity_verification as iv_api

    with iv_api._reference_cache_lock:
        hit = iv_api._reference_cache.get(url)
        return hit[1] if hit else None


def _urlopen_returning(payload):
    mock_resp = MagicMock()
    mock_resp.__enter__.return_value.read.return_value = payload
    mock_resp.__exit__.return_value = False
    return patch(
        "app.api.v1.identity_verification.urllib.request.urlopen",
        return_value=mock_resp,
    )


def iv_dl(url):
    from app.api.v1.identity_verification import _download_reference_image

    return _download_reference_image(url)


# ---------------------------------------------------------------------------
# 1. Cloudinary must actually overwrite deterministic keys
# ---------------------------------------------------------------------------


class TestCloudinaryOverwrite:
    def test_save_requests_overwrite_and_invalidate(self, monkeypatch):
        _set_cloudinary_env(monkeypatch)
        with patch(
            "cloudinary.uploader.upload",
            return_value={
                "secure_url": "https://res.cloudinary.com/test-cloud/raw/upload/x.jpg",
            },
        ) as upload:
            url = CloudinaryStorage().save(
                "face-references/attempt-1.jpg", b"new-reference-bytes"
            )

        assert url == "https://res.cloudinary.com/test-cloud/raw/upload/x.jpg"
        upload.assert_called_once()
        args, kwargs = upload.call_args
        assert args[0] == b"new-reference-bytes"
        assert kwargs["public_id"] == "face-references/attempt-1.jpg"
        # The exact regression: overwrite=False silently discarded replacements.
        assert kwargs["overwrite"] is True
        # CDN copy must be purged so consumers fetch the new bytes.
        assert kwargs["invalidate"] is True
        assert kwargs["resource"] == "raw"

    def test_settings_credentials_used_when_environ_empty(self, monkeypatch):
        """`.env` values live on Settings, not os.environ. Save must still upload."""
        from types import SimpleNamespace

        monkeypatch.delenv("CLOUDINARY_CLOUD_NAME", raising=False)
        monkeypatch.delenv("CLOUDINARY_API_KEY", raising=False)
        monkeypatch.delenv("CLOUDINARY_API_SECRET", raising=False)
        monkeypatch.setattr(
            "app.core.config.get_settings",
            lambda: SimpleNamespace(
                CLOUDINARY_CLOUD_NAME="from-settings",
                CLOUDINARY_API_KEY="settings-key",
                CLOUDINARY_API_SECRET="settings-secret",
            ),
        )
        with patch("cloudinary.config") as cfg, patch(
            "cloudinary.uploader.upload",
            return_value={
                "secure_url": "https://res.cloudinary.com/from-settings/image/upload/v2/x.jpg",
            },
        ) as upload:
            url = CloudinaryStorage().save(
                "face-references/attempt-9.jpg", b"new-reference-bytes"
            )

        assert url.startswith("https://res.cloudinary.com/")
        cfg.assert_called_once()
        assert cfg.call_args.kwargs["cloud_name"] == "from-settings"
        upload.assert_called_once()
        assert upload.call_args.kwargs["overwrite"] is True

    def test_discarded_upload_is_a_hard_error(self, monkeypatch):
        _set_cloudinary_env(monkeypatch)
        with patch(
            "cloudinary.uploader.upload",
            return_value={
                "existing": True,
                "secure_url": "https://res.cloudinary.com/test-cloud/raw/upload/stale.jpg",
            },
        ):
            with pytest.raises(RuntimeError) as exc:
                CloudinaryStorage().save(
                    "face-references/attempt-1.jpg", b"new-reference-bytes"
                )

        # The SDK reported the bytes were discarded → loud failure, never a
        # silent return of the stale asset.
        assert exc.value.__cause__ is not None
        assert "existing asset" in str(exc.value.__cause__)
        assert "not stored" in str(exc.value.__cause__)


# ---------------------------------------------------------------------------
# 2. Re-upload with the same URL must invalidate the reference cache
# ---------------------------------------------------------------------------


class TestReferenceCacheInvalidation:
    def test_reupload_same_url_forces_fresh_download(self, client, db):
        env = _mk_attempt(db)
        attempt = env.attempt
        url = STABLE_URL

        # Prime the cache with the OLD bytes (as a prior verify-face would).
        _seed_cache(url, b"OLD-REFERENCE-BYTES")
        # Cache hit must not touch the network.
        with patch(
            "app.api.v1.identity_verification.urllib.request.urlopen",
            side_effect=AssertionError("network fetch on cache hit"),
        ):
            assert iv_dl(url) == b"OLD-REFERENCE-BYTES"

        # Re-upload via the standard endpoint. Deterministic key → the
        # storage backend returns the SAME URL for the replacement bytes.
        with patch(
            "app.storage.cloudinary.CloudinaryStorage.save",
            return_value=url,
        ) as save:
            resp = client.post(
                REFERENCE_FACE_URL.format(attempt_id=attempt.id),
                json={
                    "reference_image": _png_b64(),
                    "image_format": "image/png",
                },
            )

        assert resp.status_code == 200, resp.text
        save.assert_called_once()
        assert resp.json()["reference_face_url"] == url
        # The stale cache entry must be gone — next download fetches anew.
        assert _cached_bytes(url) is None

        # Fresh download now returns the replacement bytes.
        with _urlopen_returning(b"NEW-REFERENCE-BYTES") as urlopen:
            assert iv_dl(url) == b"NEW-REFERENCE-BYTES"
        urlopen.assert_called_once_with(url, timeout=30)

        # And those new bytes are now the cached copy.
        assert _cached_bytes(url) == b"NEW-REFERENCE-BYTES"
