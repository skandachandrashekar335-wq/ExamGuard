"""Regression tests A–J for demo freshness, Start Exam, RBAC and storage.

A. fresh demo has no references
B. uploaded reference persists
C. reload demo removes previous reference association (and deletes the asset)
D. fresh demo has no previous verification state
E. Start Exam transitions correctly (NOT_STARTED → IN_PROGRESS; refresh preserves)
F. unauthorized Start Exam is rejected
G. Start Exam failure produces a useful error, never a fake success
H. RBAC remains intact
I. Cloudinary behavior remains correct (only demo face-reference assets deleted)
J. face verification records / non-demo data remain intact
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth import Role, get_current_user
from app.main import app

LOAD = "/api/v1/demo/load"
RESET = "/api/v1/demo/reset"
STATUS = "/api/v1/demo/status"
UPLOAD = "/api/v1/demo/upload-reference-face"
SESSION_STATUS = "/api/v1/demo/session-status"
INVIG_DASHBOARD = "/api/v1/invigilator/dashboard"
INVIG_START = "/api/v1/invigilator/start-exam"

PNG_1PX_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBg"
    "AAAABQABh6FO1AAAAABJRU5ErkJggg=="
)
STALE_URL = "https://res.cloudinary.com/democloud/raw/upload/v123/ExamGuard/face-references/attempt-77.jpg"


def _load(client: TestClient) -> dict:
    resp = client.post(LOAD)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _as_role(user) -> None:
    """Point the auth override at a specific DB user/role for one test."""
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(user.id),
        "role": user.role,
        "email": user.email,
        "full_name": user.full_name,
    }


def _make_user(db, email: str, role: str, firebase_uid: str | None = None):
    from app.models import User

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            full_name=email.split("@")[0],
            firebase_uid=firebase_uid,
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
    db.refresh(user)
    return user


class TestFreshDemo:
    """A, C, D — fresh demo baseline."""

    def test_fresh_demo_has_no_references(self, client):
        """A: a freshly loaded demo exposes no reference photos."""
        _load(client)
        status = client.get(STATUS).json()
        assert status["loaded"] is True
        refs = status.get("reference_face_urls")
        if refs:
            assert all(r is None for r in refs), refs

        from app.core.database import SessionLocal
        from app.models import IdentityVerificationAttempt

        db = SessionLocal()
        try:
            load = _load(client)
            rows = (
                db.query(IdentityVerificationAttempt)
                .filter(
                    IdentityVerificationAttempt.id.in_(load["demo_attempt_ids"])
                )
                .all()
            )
            for row in rows:
                assert row.reference_face_url is None
                assert row.status == "CREATED"
                assert row.decision == "PENDING"
        finally:
            db.close()

    def test_reload_removes_previous_reference_and_deletes_asset(self, client):
        """C: reloading the demo detaches previous references and asks
        storage to delete exactly the stale demo assets."""
        load = _load(client)
        attempt_id = load["demo_attempt_ids"][0]

        with patch(
            "app.storage.cloudinary.CloudinaryStorage.save",
            return_value=STALE_URL,
        ):
            resp = client.post(
                UPLOAD,
                json={
                    "attempt_id": attempt_id,
                    "reference_image": PNG_1PX_B64,
                    "image_format": "image/png",
                },
            )
        assert resp.status_code == 200, resp.text
        before = client.get(STATUS).json()["reference_face_urls"]
        assert before[0] == STALE_URL

        with patch("app.api.v1.demo._delete_reference_assets") as delete_mock:
            _load(client)
        delete_mock.assert_called_once()
        stale_urls = delete_mock.call_args[0][0]
        assert STALE_URL in stale_urls

        after = client.get(STATUS).json()["reference_face_urls"]
        assert all(r is None for r in after), after

    def test_fresh_demo_has_no_previous_verification_state(self, client):
        """D: gate/entry/attendance/security/evidence rows and non-fresh
        attempt/session state from the previous demo are cleared."""
        from app.core.database import SessionLocal
        from app.models import (
            AttendanceEvent,
            AttendanceRecord,
            EntryVerification,
            GateEvent,
            IdentityVerificationAttempt,
            IdentityVerificationEvidence,
            SecurityAlert,
            SecurityEvent,
        )
        from app.models.proxy_risk import ProxyRiskAssessment, SecuritySignal

        load = _load(client)
        attempt_id = load["demo_attempt_ids"][0]
        session_id = load["demo_session_id"]
        exam_id = load["demo_exam_id"]
        hall_id = load["demo_hall_id"]

        # Start the session so state is non-fresh
        assert client.post(
            "/api/v1/demo/start-session", json={"performed_by": "tester"}
        ).status_code == 200

        db = SessionLocal()
        try:
            attempt = db.get(IdentityVerificationAttempt, attempt_id)
            student_id = attempt.student_id
            reg_id = attempt.exam_registration_id

            attempt.status = "COMPLETED"
            attempt.decision = "MATCH"
            attempt.reference_face_url = STALE_URL
            attempt.started_at = datetime.now(timezone.utc)
            attempt.completed_at = datetime.now(timezone.utc)

            evidence = IdentityVerificationEvidence(
                attempt_id=attempt_id,
                signal_type="similarity_score",
                signal_value="0.97",
            )
            db.add(evidence)

            gate = GateEvent(
                session_id=session_id,
                previous_status="GATES_CLOSED",
                new_status="GATES_OPEN",
            )
            db.add(gate)
            db.flush()

            entry = EntryVerification(
                student_id=student_id,
                exam_registration_id=reg_id,
                exam_hall_id=hall_id,
                entry_point_id=_demo_entry_point_id(db),
            )
            db.add(entry)
            db.flush()

            attendance = AttendanceRecord(
                student_id=student_id,
                exam_id=exam_id,
                exam_registration_id=reg_id,
                entry_verification_id=entry.id,
                entry_method="VERIFIED_ENTRY",
                entry_time=datetime.now(timezone.utc),
                hall_id=hall_id,
                session_id=session_id,
            )
            db.add(attendance)
            db.add(
                AttendanceEvent(
                    student_id=student_id,
                    exam_id=exam_id,
                    exam_registration_id=reg_id,
                    entry_verification_id=entry.id,
                    event_type="ENTRY",
                    status_snapshot="PRESENT",
                )
            )

            security_event = SecurityEvent(
                event_type="UNUSUAL_PATTERN",
                severity="LOW",
                entity_type="student",
                entity_id=student_id,
                exam_id=exam_id,
                hall_id=hall_id,
                entry_verification_id=entry.id,
                source="test",
            )
            db.add(security_event)
            db.flush()
            db.add(
                SecurityAlert(
                    security_event_id=security_event.id,
                    severity="LOW",
                    message="demo alert",
                )
            )
            db.add(
                SecuritySignal(
                    entry_verification_id=entry.id,
                    signal_type="RAPID_ENTRY",
                    strength="MODERATE",
                    source="test",
                )
            )
            db.add(
                ProxyRiskAssessment(
                    entry_verification_id=entry.id,
                    risk_level="LOW",
                    risk_score=0.1,
                )
            )
            db.commit()
            seeded_ev_id = entry.id
        finally:
            db.close()

        with patch("app.api.v1.demo._delete_reference_assets"):
            _load(client)

        db = SessionLocal()
        try:
            from app.models import ExaminationSession

            session = db.get(ExaminationSession, session_id)
            assert session.status == "NOT_STARTED"
            assert session.gate_status == "GATES_CLOSED"
            assert session.started_at is None
            assert session.ended_at is None

            attempt = db.get(IdentityVerificationAttempt, attempt_id)
            assert attempt.status == "CREATED"
            assert attempt.decision == "PENDING"
            assert attempt.reference_face_url is None
            assert attempt.started_at is None
            assert attempt.completed_at is None

            assert (
                db.query(IdentityVerificationEvidence)
                .filter_by(attempt_id=attempt_id)
                .count()
                == 0
            )
            assert db.query(GateEvent).filter_by(session_id=session_id).count() == 0
            assert (
                db.query(EntryVerification).filter_by(id=seeded_ev_id).count() == 0
            )
            assert (
                db.query(AttendanceRecord).filter_by(session_id=session_id).count()
                == 0
            )
            assert (
                db.query(AttendanceEvent).filter_by(exam_id=exam_id).count() == 0
            )
            assert (
                db.query(SecurityEvent).filter_by(exam_id=exam_id).count() == 0
            )
        finally:
            db.close()


def _demo_entry_point_id(db) -> int:
    from app.api.v1.demo import DEMO_ENTRY_CODE
    from app.models import EntryPoint

    ep = db.query(EntryPoint).filter_by(code=DEMO_ENTRY_CODE).first()
    assert ep is not None, "demo entry point missing"
    return ep.id


class TestStartExam:
    """E, F, G — invigilator Start Exam behaviour."""

    def test_start_exam_transitions_and_refresh_preserves(self, client):
        """E: dashboard reports can_start; POST /start-exam performs the
        real NOT_STARTED → IN_PROGRESS transition; refreshes preserve it."""
        from app.core.database import SessionLocal

        db = SessionLocal()
        try:
            user = _make_user(
                db, "inv.start@example.com", Role.INVIGILATOR
            )
        finally:
            db.close()

        _as_role(user)
        _load(client)

        dash = client.get(INVIG_DASHBOARD)
        assert dash.status_code == 200, dash.text
        body = dash.json()
        assert body["profile"]["session_status"] == "NOT_STARTED"
        assert body["can_start"] is True
        assert body["session_active"] is False

        resp = client.post(INVIG_START, json={"performed_by": "tester"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "started"

        # Refresh preserves IN_PROGRESS (GETs never mutate)
        for _ in range(2):
            dash = client.get(INVIG_DASHBOARD).json()
            assert dash["profile"]["session_status"] == "IN_PROGRESS"
            assert dash["session_active"] is True
            assert dash["can_end"] is True
            assert dash["can_start"] is False

        status = client.get(SESSION_STATUS).json()
        assert status["session_status"] == "IN_PROGRESS"

    def test_unauthorized_start_exam_rejected(self, client):
        """F: non-invigilator roles and invigilators without an assignment
        cannot start the exam."""
        from app.core.database import SessionLocal

        db = SessionLocal()
        try:
            reviewer = _make_user(db, "rev.nostart@example.com", Role.REVIEWER)
        finally:
            db.close()

        _as_role(reviewer)
        _load(client)

        resp = client.post(INVIG_START, json={})
        assert resp.status_code == 403, resp.text

        # INVIGILATOR role but no assignment → 404, not a silent success
        from app.core.database import SessionLocal as SL

        db = SL()
        try:
            orphan = _make_user(db, "inv.orphan@example.com", Role.INVIGILATOR)
        finally:
            db.close()
        _as_role(orphan)
        resp = client.post(INVIG_START, json={})
        assert resp.status_code == 404, resp.text

    def test_start_exam_failure_produces_error_not_fake_success(self, client):
        """G: window violations and invalid transitions return 422 with a
        detail message and never fabricate a started session."""
        from app.core.database import SessionLocal
        from app.models import Exam, ExaminationSession

        db = SessionLocal()
        try:
            user = _make_user(db, "inv.fail@example.com", Role.INVIGILATOR)
        finally:
            db.close()
        _as_role(user)
        load = _load(client)

        # Move the exam window entirely into the past
        db = SessionLocal()
        try:
            from datetime import time as dt_time

            exam = db.get(Exam, load["demo_exam_id"])
            exam.exam_date = (datetime.now(timezone.utc) - timedelta(days=2)).date()
            exam.start_time = dt_time(9, 0)
            exam.end_time = dt_time(11, 0)
            db.commit()
        finally:
            db.close()

        resp = client.post(INVIG_START, json={})
        assert resp.status_code == 422, resp.text
        assert "detail" in resp.json()

        db = SessionLocal()
        try:
            session = db.get(
                ExaminationSession, load["demo_session_id"]
            )
            assert session.status == "NOT_STARTED", "no fake success"
        finally:
            db.close()

        # Restore today's full-day window, start once, then a second start
        # must fail with an error while the session truthfully stays
        # IN_PROGRESS.
        db = SessionLocal()
        try:
            from datetime import time as dt_time

            exam = db.get(Exam, load["demo_exam_id"])
            exam.exam_date = datetime.now(timezone.utc).date()
            exam.start_time = dt_time(0, 0)
            exam.end_time = dt_time(23, 59, 59, 999999)
            db.commit()
        finally:
            db.close()

        assert client.post(INVIG_START, json={}).status_code == 200
        second = client.post(INVIG_START, json={})
        assert second.status_code == 422, second.text
        assert second.json()["detail"]

        db = SessionLocal()
        try:
            session = db.get(
                ExaminationSession, load["demo_session_id"]
            )
            assert session.status == "IN_PROGRESS"
        finally:
            db.close()


class TestRBAC:
    """H — authorization surface unchanged."""

    def test_rbac_remains_intact(self, client):
        from app.core.database import SessionLocal

        db = SessionLocal()
        try:
            invigilator = _make_user(db, "inv.rbac@example.com", Role.INVIGILATOR)
        finally:
            db.close()
        _as_role(invigilator)

        # INVIGILATOR is not allowed on admin-only endpoints
        resp = client.post("/api/v1/exams", json={"exam_name": "X"})
        assert resp.status_code == 403, resp.text

        # Unauthenticated requests are rejected by real auth (no bypass)
        app.dependency_overrides.pop(get_current_user, None)
        resp = client.post(LOAD)
        assert resp.status_code in (401, 403), resp.text

    def test_non_demo_attempt_upload_rejected(self, client):
        """Demo-scoped upload still refuses non-demo attempts."""
        _load(client)
        resp = client.post(
            UPLOAD,
            json={
                "attempt_id": 999999,
                "reference_image": PNG_1PX_B64,
                "image_format": "image/png",
            },
        )
        assert resp.status_code == 422


class TestCloudinary:
    """I — storage behaviour and demo-only asset deletion."""

    def test_public_id_parsing_only_matches_demo_face_references(self):
        from app.api.v1.demo import _reference_public_id

        assert (
            _reference_public_id(
                "https://res.cloudinary.com/demo/raw/upload/v123456/"
                "examguard/face-references/attempt-12.jpg"
            )
            == "examguard/face-references/attempt-12.jpg"
        )
        assert (
            _reference_public_id(
                "https://res.cloudinary.com/demo/raw/upload/"
                "examguard/face-references/attempt-3.png"
            )
            == "examguard/face-references/attempt-3.png"
        )
        # Non-demo assets are never selectable
        assert (
            _reference_public_id(
                "https://res.cloudinary.com/demo/raw/upload/v9/documents/real.pdf"
            )
            is None
        )
        assert (
            _reference_public_id("https://example.com/some/page") is None
        )
        # Relative storage keys are never selectable
        assert _reference_public_id("face-references/attempt-1.jpg") is None
        assert _reference_public_id(None) is None  # type: ignore[arg-type]

    def test_delete_assets_invokes_storage_with_parsed_public_id(self):
        from app.api.v1.demo import _delete_reference_assets

        with patch(
            "app.storage.cloudinary.CloudinaryStorage.delete"
        ) as delete_mock:
            removed = _delete_reference_assets(
                [
                    STALE_URL,
                    "https://example.com/not-ours.png",
                    "not-a-url",
                ]
            )
        assert removed == 1
        delete_mock.assert_called_once_with(
            "ExamGuard/face-references/attempt-77.jpg"
        )

    def test_delete_assets_retries_without_appended_format(self):
        """Cloudinary image delivery URLs append the format, so a URL-derived
        public_id can carry one extension too many; the exact-id attempt is
        retried once without it and only a confirmed deletion counts."""
        from app.api.v1.demo import _delete_reference_assets

        url = (
            "https://res.cloudinary.com/demo/image/upload/v99/"
            "examguard/face-references/attempt-5.png.png"
        )
        with patch(
            "app.storage.cloudinary.CloudinaryStorage.delete",
            side_effect=[False, True],
        ) as delete_mock:
            removed = _delete_reference_assets([url])
        assert removed == 1
        assert [c.args for c in delete_mock.call_args_list] == [
            ("examguard/face-references/attempt-5.png.png",),
            ("examguard/face-references/attempt-5.png",),
        ]

    def test_delete_assets_reports_zero_when_nothing_confirmed(self):
        from app.api.v1.demo import _delete_reference_assets

        url = (
            "https://res.cloudinary.com/demo/image/upload/v99/"
            "examguard/face-references/attempt-6.jpg"
        )
        with patch(
            "app.storage.cloudinary.CloudinaryStorage.delete",
            side_effect=[False, False],
        ) as delete_mock:
            removed = _delete_reference_assets([url])
        assert removed == 0
        assert delete_mock.call_count == 2

    def test_cloudinary_delete_returns_confirmation(self, monkeypatch):
        """delete() reports True only for a confirmed destroy; not-found and
        transport errors are False, never raised."""
        from app.storage.cloudinary import CloudinaryStorage

        monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "testcloud")
        monkeypatch.setenv("CLOUDINARY_API_KEY", "k")
        monkeypatch.setenv("CLOUDINARY_API_SECRET", "s")
        storage = CloudinaryStorage()
        assert storage._using_cloudinary is True

        with patch(
            "cloudinary.uploader.destroy",
            return_value={"result": "ok"},
        ) as destroy_mock:
            assert storage.delete("face-references/attempt-1.png") is True
            destroy_mock.assert_called_once()

        with patch(
            "cloudinary.uploader.destroy",
            return_value={"result": "not found"},
        ) as destroy_mock:
            assert storage.delete("face-references/attempt-2.png") is False
            assert destroy_mock.call_count == 2  # image then raw

        with patch(
            "cloudinary.uploader.destroy",
            side_effect=RuntimeError("network down"),
        ):
            assert storage.delete("face-references/attempt-3.png") is False

    def test_upload_rejects_non_http_storage_result(self, client):
        """Absolute HTTPS reference URLs remain mandatory."""
        load = _load(client)
        with patch(
            "app.storage.cloudinary.CloudinaryStorage.save",
            return_value="face-references/attempt-1.jpg",
        ):
            resp = client.post(
                UPLOAD,
                json={
                    "attempt_id": load["demo_attempt_ids"][0],
                    "reference_image": PNG_1PX_B64,
                    "image_format": "image/png",
                },
            )
        assert resp.status_code == 502

    def test_relative_reference_urls_are_never_sent_to_storage(self, client):
        """A legacy relative key on a demo attempt is detached without
        triggering any storage deletion."""
        from app.core.database import SessionLocal
        from app.models import IdentityVerificationAttempt

        load = _load(client)
        attempt_id = load["demo_attempt_ids"][0]

        db = SessionLocal()
        try:
            attempt = db.get(IdentityVerificationAttempt, attempt_id)
            attempt.reference_face_url = "face-references/attempt-1.jpg"
            db.commit()
        finally:
            db.close()

        with patch("app.api.v1.demo._delete_reference_assets") as delete_mock:
            _load(client)
        delete_mock.assert_not_called()

        db = SessionLocal()
        try:
            attempt = db.get(IdentityVerificationAttempt, attempt_id)
            assert attempt.reference_face_url is None
        finally:
            db.close()

    def test_reset_deletes_assets_and_clears_runtime_rows(self, client):
        """Reset clears evidence/security rows and deletes demo assets."""
        from app.core.database import SessionLocal
        from app.models import (
            IdentityVerificationAttempt,
            IdentityVerificationEvidence,
            SecurityEvent,
        )

        load = _load(client)
        attempt_id = load["demo_attempt_ids"][0]
        exam_id = load["demo_exam_id"]

        with patch(
            "app.storage.cloudinary.CloudinaryStorage.save",
            return_value=STALE_URL,
        ):
            resp = client.post(
                UPLOAD,
                json={
                    "attempt_id": attempt_id,
                    "reference_image": PNG_1PX_B64,
                    "image_format": "image/png",
                },
            )
        assert resp.status_code == 200, resp.text

        db = SessionLocal()
        try:
            db.add(
                IdentityVerificationEvidence(
                    attempt_id=attempt_id,
                    signal_type="similarity_score",
                    signal_value="0.5",
                )
            )
            db.add(
                SecurityEvent(
                    event_type="MANUAL_FLAG",
                    severity="INFO",
                    entity_type="exam",
                    entity_id=exam_id,
                    exam_id=exam_id,
                    source="test",
                )
            )
            db.commit()
        finally:
            db.close()

        with patch("app.api.v1.demo._delete_reference_assets") as delete_mock:
            resp = client.post(RESET)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "reset"
        delete_mock.assert_called_once()
        assert STALE_URL in delete_mock.call_args[0][0]

        db = SessionLocal()
        try:
            assert (
                db.query(IdentityVerificationEvidence)
                .filter_by(attempt_id=attempt_id)
                .count()
                == 0
            )
            assert db.query(SecurityEvent).filter_by(exam_id=exam_id).count() == 0
            assert (
                db.query(IdentityVerificationAttempt)
                .filter_by(id=attempt_id)
                .count()
                == 0
            )
        finally:
            db.close()


class TestFaceVerificationIntact:
    """J — face-verification records survive demo operations."""

    def test_load_preserves_non_demo_verification_records(self, client):
        """Demo load never touches real exams, attempts, references or
        evidence — the face-verification pipeline data stays intact."""
        from app.core.database import SessionLocal
        from app.models import (
            Exam,
            ExamHall,
            ExamRegistration,
            IdentityVerificationAttempt,
            IdentityVerificationEvidence,
            Student,
            Subject,
        )

        db = SessionLocal()
        try:
            from datetime import time as dt_time

            subject = Subject(
                code="REAL-MA",
                name="Real Exam Subject",
                department="Real",
                semester=1,
                credits=3,
                is_active=True,
            )
            db.add(subject)
            db.flush()
            exam = Exam(
                subject_id=subject.id,
                exam_name="Real Exam",
                exam_date=datetime.now(timezone.utc).date(),
                start_time=dt_time(9, 0),
                end_time=dt_time(11, 0),
                semester=1,
                department="Real",
                is_active=True,
            )
            db.add(exam)
            db.flush()
            student = Student(usn="REAL001", name="Real Student")
            db.add(student)
            db.flush()
            hall = ExamHall(
                building="Real Building",
                room_number="R1",
                name="Real Hall",
                capacity=30,
                rows=5,
                columns=6,
                is_active=True,
            )
            db.add(hall)
            db.flush()
            reg = ExamRegistration(
                student_id=student.id, exam_id=exam.id, status="REGISTERED"
            )
            db.add(reg)
            db.flush()
            attempt = IdentityVerificationAttempt(
                student_id=student.id,
                exam_registration_id=reg.id,
                status="COMPLETED",
                verification_method="FACE",
                decision="MATCH",
                reference_face_url="https://res.cloudinary.com/demo/raw/upload/"
                "face-references/attempt-9999.jpg",
            )
            db.add(attempt)
            db.flush()
            evidence = IdentityVerificationEvidence(
                attempt_id=attempt.id,
                signal_type="similarity_score",
                signal_value="0.99",
                provider_name="uniface",
            )
            db.add(evidence)
            db.commit()
            real_attempt_id = attempt.id
            real_evidence_id = evidence.id
        finally:
            db.close()

        with patch("app.api.v1.demo._delete_reference_assets"):
            _load(client)

        db = SessionLocal()
        try:
            attempt = db.get(IdentityVerificationAttempt, real_attempt_id)
            assert attempt is not None
            assert attempt.status == "COMPLETED"
            assert attempt.decision == "MATCH"
            assert attempt.reference_face_url is not None
            evidence = db.get(
                IdentityVerificationEvidence, real_evidence_id
            )
            assert evidence is not None
            assert evidence.signal_value == "0.99"
            assert db.query(Student).filter_by(usn="REAL001").count() == 1
        finally:
            db.close()

    def test_fresh_demo_attempt_ready_for_face_pipeline(self, client):
        """A freshly loaded demo attempt satisfies the pipeline's entry
        preconditions (CREATED / PENDING / FACE) — no fake results."""
        from app.models.identity_verification import (
            STATUS_TRANSITIONS,
            IdentityVerificationStatus,
        )

        load = _load(client)
        from app.core.database import SessionLocal
        from app.models import IdentityVerificationAttempt

        db = SessionLocal()
        try:
            attempt = db.get(
                IdentityVerificationAttempt, load["demo_attempt_ids"][0]
            )
            assert attempt.status == IdentityVerificationStatus.CREATED.value
            assert attempt.decision == "PENDING"
            assert attempt.verification_method == "FACE"
            assert (
                IdentityVerificationStatus.IN_PROGRESS.value
                in STATUS_TRANSITIONS[attempt.status]
            )
        finally:
            db.close()
