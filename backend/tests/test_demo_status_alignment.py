"""demo_status must stay index-aligned when a registration has >1 attempt.

Part 16 / Problem B: demo_status used to zip flat id lists built by separate
queries (students vs attempts, no ORDER BY on Student). REVERIFY creates a
follow-up attempt for the same registration, which exposed the drift —
demo_student_usns[i] could name a different student than
demo_attempt_ids[i]. The status payload must report the LATEST attempt per
registration, aligned with its student, in deterministic order.
"""

import pytest

from app.core.database import SessionLocal
from app.models.exam_registration import ExamRegistration
from app.models.identity_verification import IdentityVerificationAttempt
from app.models.student import Student

DEMO_LOAD_URL = "/api/v1/demo/load"
DEMO_STATUS_URL = "/api/v1/demo/status"
DEMO_RESET_URL = "/api/v1/demo/reset"
NEW_URL = "https://example.com/ppi-demo-replacement.png"


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()


def _latest_attempt_id(db, student_id, exam_id):
    reg = (
        db.query(ExamRegistration)
        .filter(
            ExamRegistration.student_id == student_id,
            ExamRegistration.exam_id == exam_id,
        )
        .one()
    )
    return (
        db.query(IdentityVerificationAttempt)
        .filter(
            IdentityVerificationAttempt.exam_registration_id == reg.id
        )
        .order_by(IdentityVerificationAttempt.id.desc())
        .first()
        .id
    )


def test_demo_status_latest_attempt_per_registration_aligned(client, db):
    client.post(DEMO_RESET_URL)
    try:
        load = client.post(DEMO_LOAD_URL).json()
        exam_id = load["demo_exam_id"]
        original_ids = list(load["demo_attempt_ids"])

        # A REVERIFY-style follow-up attempt for DEMO001's registration.
        demo001 = (
            db.query(Student).filter(Student.usn == "DEMO001").one()
        )
        reg = (
            db.query(ExamRegistration)
            .filter(
                ExamRegistration.student_id == demo001.id,
                ExamRegistration.exam_id == exam_id,
            )
            .one()
        )
        new_attempt = IdentityVerificationAttempt(
            student_id=demo001.id,
            exam_registration_id=reg.id,
            status="COMPLETED",
            decision="INCONCLUSIVE",
            verification_method="FACE",
            reference_face_url=NEW_URL,
        )
        db.add(new_attempt)
        db.commit()
        db.refresh(new_attempt)
        assert new_attempt.id > max(original_ids)

        status = client.get(DEMO_STATUS_URL).json()

        assert status["loaded"] is True
        assert status["demo_student_usns"] == ["DEMO001", "DEMO002", "DEMO003"]

        # Index 0 is the NEWEST attempt for DEMO001's registration, and the
        # reference URL at the same index is the replacement URL.
        assert status["demo_attempt_ids"][0] == new_attempt.id
        assert status["reference_face_urls"][0] == NEW_URL

        # Every other slot still shows that student's own latest attempt —
        # not whichever attempt happened to come back from an unordered
        # query.
        usns = status["demo_student_usns"]
        for i, usn in enumerate(usns):
            student = db.query(Student).filter(Student.usn == usn).one()
            assert status["demo_attempt_ids"][i] == _latest_attempt_id(
                db, student.id, exam_id
            )

        # Parallel lists stay the same length (index-zipped consumers).
        assert (
            len(status["demo_student_ids"])
            == len(status["demo_student_usns"])
            == len(status["demo_attempt_ids"])
            == len(status["reference_face_urls"])
            == 3
        )
    finally:
        client.post(DEMO_RESET_URL)
        client.post(DEMO_LOAD_URL)


def test_renamed_demo_candidate_stays_attached_to_reference(client, db):
    """Editing USN/name must not drop the candidate or their attempt."""
    client.post(DEMO_RESET_URL)
    try:
        client.post(DEMO_LOAD_URL)
        student = db.query(Student).filter(Student.usn == "DEMO001").one()
        before = client.get(DEMO_STATUS_URL).json()
        index = before["demo_student_usns"].index("DEMO001")
        attempt_id = before["demo_attempt_ids"][index]
        reference = before["reference_face_urls"][index]

        patched = client.patch(
            f"/api/v1/students/{student.id}",
            json={"usn": "TEST001", "name": "Test Candidate Alpha"},
        )
        assert patched.status_code == 200
        assert patched.json()["id"] == student.id

        status = client.get(DEMO_STATUS_URL).json()
        assert status["demo_student_usns"].count("TEST001") == 1
        renamed_at = status["demo_student_usns"].index("TEST001")
        assert status["demo_student_names"][renamed_at] == "Test Candidate Alpha"
        assert status["demo_attempt_ids"][renamed_at] == attempt_id
        assert status["reference_face_urls"][renamed_at] == reference
        assert status["demo_student_ids"][renamed_at] == student.id

        from app.api.v1.demo import _is_demo_attempt

        db.expire_all()
        assert _is_demo_attempt(db, attempt_id) is True
    finally:
        client.post(DEMO_RESET_URL)
        client.post(DEMO_LOAD_URL)
