"""Live-frame recovery behaviour for face verification.

Probe frames without a usable face must not permanently fail the attempt —
the invigilator UX re-captures until the subject is positioned correctly.
"""

from __future__ import annotations

from datetime import date, time
from unittest.mock import patch

import cv2
import numpy as np
import pytest
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationEvidence,
    IdentityVerificationStatus,
)
from app.services.face_verification import (
    DeterministicProvider,
    FaceVerificationError,
    FaceVerificationErrorType,
    ProviderUnavailableError,
)
from app.services import identity_verification as iv_service
from app.services.identity_verification import (
    create_attempt,
    get_attempt,
    get_rate_limiter,
    start_attempt,
    verify_face,
)
from app.schemas.identity_verification import IdentityVerificationCreate
from app.core.config import get_settings


def _make_valid_jpeg(width: int = 100, height: int = 100) -> bytes:
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[25:75, 25:75] = (200, 180, 160)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


FAKE_JPEG = _make_valid_jpeg()


@pytest.fixture(autouse=True)
def cleanup():
    db = SessionLocal()
    try:
        db.execute(delete(IdentityVerificationEvidence))
        db.execute(delete(IdentityVerificationAttempt))
        from app.models.exam_registration import ExamRegistration
        from app.models.hall_ticket import HallTicket
        from app.models.student import Student
        from app.models.exam import Exam
        from app.models.subject import Subject
        db.execute(delete(HallTicket))
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("LR%"))
            )
        ))
        db.execute(delete(Student).where(Student.usn.ilike("LR%")))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("LR%")))
        db.execute(delete(Subject).where(Subject.code.ilike("LR%")))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def face_attempt(db):
    from app.models.exam import Exam
    from app.models.exam_registration import ExamRegistration, RegistrationStatus
    from app.models.student import Student
    from app.models.subject import Subject

    subject = Subject(
        code="LR101", name="LR Subject", department="LR Dept",
        semester=1, credits=3,
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)

    exam = Exam(
        subject_id=subject.id, exam_name="LR Exam Final",
        exam_date=date(2026, 12, 1), start_time=time(9, 0), end_time=time(12, 0),
        semester=1, department="LR Dept",
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    student = Student(usn="LR001", name="Live Recovery Student")
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

    return create_attempt(
        db,
        IdentityVerificationCreate(
            student_id=student.id,
            exam_registration_id=reg.id,
            verification_method="FACE",
        ),
    )


def _provider_with_error(error_type: FaceVerificationErrorType, message: str):
    provider = DeterministicProvider()
    error = FaceVerificationError(error_type=error_type, message=message)
    return (
        provider,
        patch.object(provider, "verify", side_effect=ProviderUnavailableError(error)),
    )


class TestRecoverableProbeFrameErrors:
    def test_no_face_in_probe_does_not_fail_attempt(self, db, face_attempt):
        start_attempt(db, face_attempt.id)
        provider, mock_verify = _provider_with_error(
            FaceVerificationErrorType.NO_FACE_DETECTED,
            "No face detected in probe image",
        )
        with mock_verify, patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            with pytest.raises(ValueError, match="No usable face detected"):
                verify_face(
                    db,
                    face_attempt.id,
                    reference_image=FAKE_JPEG,
                    probe_image=FAKE_JPEG,
                )
        attempt = get_attempt(db, face_attempt.id)
        assert attempt.status in (
            IdentityVerificationStatus.CREATED.value,
            IdentityVerificationStatus.IN_PROGRESS.value,
        )
        assert attempt.decision == "PENDING"

    def test_multiple_faces_in_probe_does_not_fail_attempt(self, db, face_attempt):
        start_attempt(db, face_attempt.id)
        provider, mock_verify = _provider_with_error(
            FaceVerificationErrorType.MULTIPLE_FACES_DETECTED,
            "Multiple faces (2) detected in probe image",
        )
        with mock_verify, patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            with pytest.raises(ValueError, match="Multiple faces detected"):
                verify_face(
                    db,
                    face_attempt.id,
                    reference_image=FAKE_JPEG,
                    probe_image=FAKE_JPEG,
                )
        attempt = get_attempt(db, face_attempt.id)
        assert attempt.status in (
            IdentityVerificationStatus.CREATED.value,
            IdentityVerificationStatus.IN_PROGRESS.value,
        )

    def test_no_face_in_reference_still_fails_attempt(self, db, face_attempt):
        start_attempt(db, face_attempt.id)
        provider, mock_verify = _provider_with_error(
            FaceVerificationErrorType.NO_FACE_DETECTED,
            "No face detected in reference image",
        )
        with mock_verify, patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            with pytest.raises(ValueError, match="stored reference"):
                verify_face(
                    db,
                    face_attempt.id,
                    reference_image=FAKE_JPEG,
                    probe_image=FAKE_JPEG,
                )
        attempt = get_attempt(db, face_attempt.id)
        assert attempt.status == IdentityVerificationStatus.FAILED.value

    def test_recoverable_errors_do_not_consume_attempt_budget(self, db, face_attempt):
        start_attempt(db, face_attempt.id)
        provider, mock_verify = _provider_with_error(
            FaceVerificationErrorType.NO_FACE_DETECTED,
            "No face detected in probe image",
        )
        max_calls = get_settings().FACE_VERIFICATION_MAX_CALLS_PER_ATTEMPT
        with mock_verify, patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            for _ in range(max_calls + 3):
                with pytest.raises(ValueError, match="No usable face detected"):
                    verify_face(
                        db,
                        face_attempt.id,
                        reference_image=FAKE_JPEG,
                        probe_image=FAKE_JPEG,
                    )
        assert get_rate_limiter().check_attempt_limit(
            face_attempt.id, max_calls
        ), "recoverable no-face frames must not consume attempt budget"

    def test_timeout_still_fails_attempt(self, db, face_attempt):
        start_attempt(db, face_attempt.id)
        provider, mock_verify = _provider_with_error(
            FaceVerificationErrorType.TIMEOUT,
            "Provider timed out",
        )
        with mock_verify, patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            with pytest.raises(ValueError, match="timed out"):
                verify_face(
                    db,
                    face_attempt.id,
                    reference_image=FAKE_JPEG,
                    probe_image=FAKE_JPEG,
                )
        attempt = get_attempt(db, face_attempt.id)
        assert attempt.status == IdentityVerificationStatus.FAILED.value
