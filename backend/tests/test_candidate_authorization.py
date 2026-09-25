"""Regression tests for candidate enrollment / reference-ownership validation.

Covers the invigilator face-verification authorization requirements:
- REFERENCE_MISMATCH when the attempt's registration belongs to another
  student (wrong selected candidate) or is missing/orphaned
- CANDIDATE_NOT_ENROLLED when the registration is cancelled or the student
  is inactive (student not enrolled in the current examination)
- Checks execute BEFORE any face-provider call or rate-limit consumption
- evaluate endpoint rejects unauthorized attempts too
- INVIGILATOR scope: unresolvable registration → 403 (no silent skip)
- FailureCategory contains the new codes
- Happy path (valid enrollment) still verifies normally
"""

import base64
from datetime import date, time
from unittest.mock import patch

import cv2
import numpy as np
import pytest
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.models.exam import Exam
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.hall_ticket import HallTicket
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationDecision,
    IdentityVerificationEvidence,
    IdentityVerificationMethod,
    IdentityVerificationStatus,
)
from app.models.student import Student
from app.models.subject import Subject
from app.schemas.identity_verification import IdentityVerificationCreate
from app.services.face_verification import (
    DeterministicProvider,
    get_face_verification_provider,
)
from app.services.face_verification.failure_categories import FailureCategory
from app.services.identity_verification import (
    create_attempt,
    start_attempt,
    validate_attempt_authorization,
    verify_face,
)


@pytest.fixture(autouse=True)
def cleanup():
    db = SessionLocal()
    try:
        db.execute(delete(IdentityVerificationEvidence))
        db.execute(delete(IdentityVerificationAttempt))
        db.execute(delete(HallTicket))
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("CAA%"))
            )
        ))
        db.execute(delete(Student).where(Student.usn.ilike("CAA%")))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("CAA Exam%")))
        db.execute(delete(Subject).where(Subject.code.ilike("CAA%")))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()


def _make_jpeg() -> bytes:
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[25:75, 25:75] = (200, 180, 160)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


REF_BYTES = _make_jpeg()
PROBE_BYTES = _make_jpeg()


def _mk_subject_exam_student(db, usn_suffix: str):
    subject = Subject(
        code=f"CAA{usn_suffix}", name="CAA Subject",
        department="CAA Dept", semester=1, credits=3,
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)

    exam = Exam(
        subject_id=subject.id, exam_name=f"CAA Exam {usn_suffix}",
        exam_date=date(2026, 12, 1), start_time=time(9, 0),
        end_time=time(12, 0), semester=1, department="CAA Dept",
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    student = Student(usn=f"CAA{usn_suffix}", name=f"CAA Student {usn_suffix}")
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

    return subject, exam, student, reg


@pytest.fixture()
def valid_attempt(db):
    _, _, student, reg = _mk_subject_exam_student(db, "001")
    attempt = create_attempt(
        db,
        IdentityVerificationCreate(
            student_id=student.id,
            exam_registration_id=reg.id,
            verification_method="FACE",
        ),
    )
    db.refresh(attempt)
    return attempt


# ─── FailureCategory members ───────────────────────────────────────────

class TestFailureCategoryMembers:
    def test_reference_mismatch_member(self):
        assert FailureCategory.REFERENCE_MISMATCH.value == "REFERENCE_MISMATCH"

    def test_candidate_not_enrolled_member(self):
        assert (
            FailureCategory.CANDIDATE_NOT_ENROLLED.value
            == "CANDIDATE_NOT_ENROLLED"
        )


# ─── Service: validate_attempt_authorization ───────────────────────────

class TestValidateAttemptAuthorization:
    def test_valid_attempt_passes(self, db, valid_attempt):
        validate_attempt_authorization(db, valid_attempt)

    def test_registration_belonging_to_other_student_raises_reference_mismatch(
        self, db, valid_attempt
    ):
        _, _, _, other_reg = _mk_subject_exam_student(db, "002")
        valid_attempt.exam_registration_id = other_reg.id
        db.add(valid_attempt)
        db.commit()

        attempt = db.query(IdentityVerificationAttempt).get(valid_attempt.id)
        with pytest.raises(ValueError) as exc:
            validate_attempt_authorization(db, attempt)
        assert "REFERENCE_MISMATCH" in str(exc.value)

    def test_missing_registration_raises_reference_mismatch(self, db, valid_attempt):
        valid_attempt.exam_registration_id = 999999
        db.add(valid_attempt)
        db.commit()

        attempt = db.query(IdentityVerificationAttempt).get(valid_attempt.id)
        with pytest.raises(ValueError) as exc:
            validate_attempt_authorization(db, attempt)
        assert "REFERENCE_MISMATCH" in str(exc.value)

    def test_cancelled_registration_raises_candidate_not_enrolled(
        self, db, valid_attempt
    ):
        reg = db.query(ExamRegistration).get(valid_attempt.exam_registration_id)
        reg.status = RegistrationStatus.CANCELLED.value
        db.add(reg)
        db.commit()

        attempt = db.query(IdentityVerificationAttempt).get(valid_attempt.id)
        with pytest.raises(ValueError) as exc:
            validate_attempt_authorization(db, attempt)
        assert "CANDIDATE_NOT_ENROLLED" in str(exc.value)

    def test_inactive_student_raises_candidate_not_enrolled(
        self, db, valid_attempt
    ):
        student = db.query(Student).get(valid_attempt.student_id)
        student.is_active = False
        db.add(student)
        db.commit()

        attempt = db.query(IdentityVerificationAttempt).get(valid_attempt.id)
        with pytest.raises(ValueError) as exc:
            validate_attempt_authorization(db, attempt)
        assert "CANDIDATE_NOT_ENROLLED" in str(exc.value)


# ─── Service: verify_face gates before provider ────────────────────────

class TestVerifyFaceAuthorizationGate:
    def test_cancelled_registration_blocks_provider_call(self, db, valid_attempt):
        reg = db.query(ExamRegistration).get(valid_attempt.exam_registration_id)
        reg.status = RegistrationStatus.CANCELLED.value
        db.add(reg)
        db.commit()
        start_attempt(db, valid_attempt.id)

        with patch(
            "app.services.face_verification.get_face_verification_provider"
        ) as provider_mock:
            with pytest.raises(ValueError) as exc:
                verify_face(
                    db, valid_attempt.id,
                    reference_image=REF_BYTES,
                    probe_image=PROBE_BYTES,
                )
        assert "CANDIDATE_NOT_ENROLLED" in str(exc.value)
        provider_mock.assert_not_called()

    def test_wrong_candidate_blocks_provider_call(self, db, valid_attempt):
        _, _, _, other_reg = _mk_subject_exam_student(db, "003")
        valid_attempt.exam_registration_id = other_reg.id
        db.add(valid_attempt)
        db.commit()
        start_attempt(db, valid_attempt.id)

        with patch(
            "app.services.face_verification.get_face_verification_provider"
        ) as provider_mock:
            with pytest.raises(ValueError) as exc:
                verify_face(
                    db, valid_attempt.id,
                    reference_image=REF_BYTES,
                    probe_image=PROBE_BYTES,
                )
        assert "REFERENCE_MISMATCH" in str(exc.value)
        provider_mock.assert_not_called()

    def test_valid_enrollment_still_verifies(self, db, valid_attempt):
        start_attempt(db, valid_attempt.id)
        provider = DeterministicProvider()
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            records = verify_face(
                db, valid_attempt.id,
                reference_image=REF_BYTES,
                probe_image=PROBE_BYTES,
            )
        assert len(records) > 0


# ─── API: verify-face returns coded 422s ───────────────────────────────

class TestVerifyFaceAPIAuthorization:
    def _create_face_attempt(self, client, db, usn_suffix="010"):
        _, exam, student, reg = _mk_subject_exam_student(db, usn_suffix)
        resp = client.post("/api/v1/identity-verifications", json={
            "student_id": student.id,
            "exam_registration_id": reg.id,
            "verification_method": "FACE",
        })
        assert resp.status_code == 201
        return resp.json()["id"], student, reg

    def test_reference_mismatch_returns_422_coded_detail(self, client, db):
        attempt_id, _, reg2 = self._create_face_attempt(client, db, "011")
        _, _, _, other_reg = _mk_subject_exam_student(db, "012")
        attempt = db.query(IdentityVerificationAttempt).get(attempt_id)
        attempt.exam_registration_id = other_reg.id
        db.add(attempt)
        db.commit()

        with patch(
            "app.services.face_verification.get_face_verification_provider"
        ) as provider_mock:
            resp = client.post(
                f"/api/v1/identity-verifications/{attempt_id}/verify-face",
                json={
                    "reference_image": base64.b64encode(REF_BYTES).decode(),
                    "probe_image": base64.b64encode(PROBE_BYTES).decode(),
                },
            )
        assert resp.status_code == 422
        assert "REFERENCE_MISMATCH" in resp.json()["detail"]
        provider_mock.assert_not_called()

    def test_candidate_not_enrolled_returns_422_coded_detail(self, client, db):
        attempt_id, _, reg = self._create_face_attempt(client, db, "013")
        reg.status = RegistrationStatus.CANCELLED.value
        db.add(reg)
        db.commit()

        with patch(
            "app.services.face_verification.get_face_verification_provider"
        ) as provider_mock:
            resp = client.post(
                f"/api/v1/identity-verifications/{attempt_id}/verify-face",
                json={
                    "reference_image": base64.b64encode(REF_BYTES).decode(),
                    "probe_image": base64.b64encode(PROBE_BYTES).decode(),
                },
            )
        assert resp.status_code == 422
        assert "CANDIDATE_NOT_ENROLLED" in resp.json()["detail"]
        provider_mock.assert_not_called()

    def test_valid_enrollment_happy_path_unchanged(self, client, db):
        attempt_id, _, _ = self._create_face_attempt(client, db, "014")
        start_resp = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/start"
        )
        assert start_resp.status_code == 200

        provider = DeterministicProvider()
        with patch(
            "app.services.face_verification.get_face_verification_provider",
            return_value=provider,
        ):
            resp = client.post(
                f"/api/v1/identity-verifications/{attempt_id}/verify-face",
                json={
                    "reference_image": base64.b64encode(REF_BYTES).decode(),
                    "probe_image": base64.b64encode(PROBE_BYTES).decode(),
                },
            )
        assert resp.status_code == 201
        assert len(resp.json()["evidence"]) >= 1


# ─── API: evaluate gates unauthorized attempts ─────────────────────────

class TestEvaluateAPIAuthorization:
    def test_evaluate_rejects_cancelled_registration(self, client, db):
        resp = client.post("/api/v1/identity-verifications", json={
            "student_id": (s := _mk_subject_exam_student(db, "020"))[2].id,
            "exam_registration_id": s[3].id,
            "verification_method": "FACE",
        })
        assert resp.status_code == 201
        attempt_id = resp.json()["id"]

        s[3].status = RegistrationStatus.CANCELLED.value
        db.add(s[3])
        db.commit()

        ev = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/evaluate"
        )
        assert ev.status_code == 422
        assert "CANDIDATE_NOT_ENROLLED" in ev.json()["detail"]

    def test_evaluate_rejects_wrong_candidate(self, client, db):
        _, _, student, reg = _mk_subject_exam_student(db, "021")
        resp = client.post("/api/v1/identity-verifications", json={
            "student_id": student.id,
            "exam_registration_id": reg.id,
            "verification_method": "FACE",
        })
        assert resp.status_code == 201
        attempt_id = resp.json()["id"]

        _, _, _, other_reg = _mk_subject_exam_student(db, "022")
        attempt = db.query(IdentityVerificationAttempt).get(attempt_id)
        attempt.exam_registration_id = other_reg.id
        db.add(attempt)
        db.commit()

        ev = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/evaluate"
        )
        assert ev.status_code == 422
        assert "REFERENCE_MISMATCH" in ev.json()["detail"]

    def test_evaluate_valid_attempt_still_completes(self, client, db):
        _, _, student, reg = _mk_subject_exam_student(db, "023")
        resp = client.post("/api/v1/identity-verifications", json={
            "student_id": student.id,
            "exam_registration_id": reg.id,
            "verification_method": "FACE",
        })
        assert resp.status_code == 201
        attempt_id = resp.json()["id"]

        ev = client.post(
            f"/api/v1/identity-verifications/{attempt_id}/evaluate"
        )
        assert ev.status_code == 200
        assert ev.json()["status"] == "COMPLETED"


# ─── API: INVIGILATOR scope on unresolvable registration ───────────────

class TestInvigilatorScopeUnresolvedRegistration:
    def test_invigilator_gets_403_when_registration_unresolvable(
        self, client, db, monkeypatch
    ):
        from app.auth import Role, get_current_user
        from app.main import app
        from app.models.exam_hall import ExamHall
        from app.models.invigilator_assignment import InvigilatorAssignment
        from app.models.user import User

        _, exam, _, reg = _mk_subject_exam_student(db, "030")

        user = User(
            email="caa-invigilator@example.com",
            full_name="CAA Invigilator",
            role=Role.INVIGILATOR,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        hall = ExamHall(
            building="CAA-B", room_number="301", capacity=60,
        )
        db.add(hall)
        db.commit()
        db.refresh(hall)

        assignment = InvigilatorAssignment(
            user_id=user.id, exam_id=exam.id, exam_hall_id=hall.id,
            is_active=True,
        )
        db.add(assignment)
        db.commit()
        db.refresh(assignment)

        _, _, student, own_reg = _mk_subject_exam_student(db, "031")
        resp = client.post("/api/v1/identity-verifications", json={
            "student_id": student.id,
            "exam_registration_id": own_reg.id,
            "verification_method": "FACE",
        })
        assert resp.status_code == 201
        attempt_id = resp.json()["id"]

        # Orphan the attempt's registration reference (missing registration)
        attempt = db.query(IdentityVerificationAttempt).get(attempt_id)
        attempt.exam_registration_id = 999999
        db.add(attempt)
        db.commit()

        prev_override = app.dependency_overrides.get(get_current_user)
        app.dependency_overrides[get_current_user] = lambda: {
            "sub": str(user.id),
            "role": Role.INVIGILATOR,
            "email": user.email,
            "full_name": user.full_name,
        }
        try:
            ev = client.post(
                f"/api/v1/identity-verifications/{attempt_id}/evaluate"
            )
            assert ev.status_code == 403
            assert "not linked to an assigned exam" in ev.json()["detail"]
        finally:
            if prev_override is None:
                app.dependency_overrides.pop(get_current_user, None)
            else:
                app.dependency_overrides[get_current_user] = prev_override

    def test_invigilator_can_verify_attempt_in_assigned_exam(
        self, client, db
    ):
        from app.auth import Role, get_current_user
        from app.main import app
        from app.models.exam_hall import ExamHall
        from app.models.invigilator_assignment import InvigilatorAssignment
        from app.models.user import User

        _, exam, student, reg = _mk_subject_exam_student(db, "040")

        user = User(
            email="caa-invigilator2@example.com",
            full_name="CAA Invigilator 2",
            role=Role.INVIGILATOR,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        hall = ExamHall(building="CAA-B2", room_number="401", capacity=60)
        db.add(hall)
        db.commit()
        db.refresh(hall)

        assignment = InvigilatorAssignment(
            user_id=user.id, exam_id=exam.id, exam_hall_id=hall.id,
            is_active=True,
        )
        db.add(assignment)
        db.commit()

        resp = client.post("/api/v1/identity-verifications", json={
            "student_id": student.id,
            "exam_registration_id": reg.id,
            "verification_method": "FACE",
        })
        assert resp.status_code == 201
        attempt_id = resp.json()["id"]

        prev_override = app.dependency_overrides.get(get_current_user)
        app.dependency_overrides[get_current_user] = lambda: {
            "sub": str(user.id),
            "role": Role.INVIGILATOR,
            "email": user.email,
            "full_name": user.full_name,
        }
        try:
            ev = client.post(
                f"/api/v1/identity-verifications/{attempt_id}/evaluate"
            )
            assert ev.status_code == 200
            assert ev.json()["status"] == "COMPLETED"
        finally:
            if prev_override is None:
                app.dependency_overrides.pop(get_current_user, None)
            else:
                app.dependency_overrides[get_current_user] = prev_override
