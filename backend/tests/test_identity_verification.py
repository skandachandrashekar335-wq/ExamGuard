import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.exam import Exam
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.hall_ticket import HallTicket, HallTicketStatus
from app.models.identity_verification import (
    IdentityVerificationAttempt,
    IdentityVerificationDecision,
    IdentityVerificationEvidence,
    IdentityVerificationMethod,
    IdentityVerificationStatus,
)
from app.models.student import Student
from app.models.subject import Subject


@pytest.fixture(autouse=True)
def cleanup():
    db = SessionLocal()
    try:
        db.execute(delete(IdentityVerificationEvidence))
        db.execute(delete(IdentityVerificationAttempt))
        db.execute(delete(HallTicket))
        db.execute(delete(ExamRegistration).where(
            ExamRegistration.student_id.in_(
                db.query(Student.id).filter(Student.usn.ilike("IVT%"))
            )
        ))
        db.execute(delete(Student).where(Student.usn.ilike("IVT%")))
        db.execute(delete(Exam).where(Exam.exam_name.ilike("IV Test Exam%")))
        db.execute(delete(Subject).where(Subject.code.ilike("IVT%")))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def sample_data():
    db = SessionLocal()
    try:
        subject = Subject(
            code="IVT101", name="IV Test Subject", department="IV Dept",
            semester=1, credits=3,
        )
        db.add(subject)
        db.commit()
        db.refresh(subject)

        exam = Exam(
            subject_id=subject.id, exam_name="IV Test Exam Final",
            exam_date="2026-12-01", start_time="09:00", end_time="12:00",
            semester=1, department="IV Dept",
        )
        db.add(exam)
        db.commit()
        db.refresh(exam)

        student = Student(usn="IVT001", name="IV Test Student")
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

        ht = HallTicket(
            exam_registration_id=reg.id,
            status=HallTicketStatus.MATCHED.value,
        )
        db.add(ht)
        db.commit()
        db.refresh(ht)

        return {
            "subject_id": subject.id,
            "exam_id": exam.id,
            "student_id": student.id,
            "registration_id": reg.id,
            "hall_ticket_id": ht.id,
        }
    finally:
        db.close()


class TestModel:
    def test_status_enum(self):
        assert IdentityVerificationStatus.CREATED.value == "CREATED"
        assert IdentityVerificationStatus.IN_PROGRESS.value == "IN_PROGRESS"
        assert IdentityVerificationStatus.COMPLETED.value == "COMPLETED"
        assert IdentityVerificationStatus.FAILED.value == "FAILED"
        assert IdentityVerificationStatus.CANCELLED.value == "CANCELLED"

    def test_method_enum(self):
        assert IdentityVerificationMethod.FACE.value == "FACE"
        assert IdentityVerificationMethod.MANUAL.value == "MANUAL"
        assert IdentityVerificationMethod.DOCUMENT.value == "DOCUMENT"
        assert IdentityVerificationMethod.OTHER.value == "OTHER"

    def test_decision_enum(self):
        assert IdentityVerificationDecision.PENDING.value == "PENDING"
        assert IdentityVerificationDecision.MATCH.value == "MATCH"
        assert IdentityVerificationDecision.NO_MATCH.value == "NO_MATCH"
        assert IdentityVerificationDecision.INCONCLUSIVE.value == "INCONCLUSIVE"

    def test_model_creation(self):
        attempt = IdentityVerificationAttempt(
            student_id=1,
            exam_registration_id=1,
            status=IdentityVerificationStatus.CREATED.value,
            verification_method=IdentityVerificationMethod.MANUAL.value,
            decision=IdentityVerificationDecision.PENDING.value,
        )
        assert attempt.student_id == 1
        assert attempt.status == "CREATED"
        assert attempt.decision == "PENDING"
        assert attempt.hall_ticket_id is None

    def test_repr(self):
        attempt = IdentityVerificationAttempt(
            student_id=1,
            exam_registration_id=1,
            status="CREATED",
            verification_method="MANUAL",
            decision="PENDING",
        )
        assert "IdentityVerificationAttempt" in repr(attempt)

    def test_evidence_creation(self):
        evidence = IdentityVerificationEvidence(
            attempt_id=1,
            signal_type="similarity_score",
            signal_value="0.92",
            provider_name="test_provider",
            confidence=0.92,
        )
        assert evidence.signal_type == "similarity_score"
        assert evidence.signal_value == "0.92"


class TestServiceCreate:
    def test_create_success(self, sample_data):
        from app.schemas.identity_verification import IdentityVerificationCreate
        from app.services.identity_verification import create_attempt

        db = SessionLocal()
        try:
            attempt = create_attempt(
                db,
                IdentityVerificationCreate(
                    student_id=sample_data["student_id"],
                    exam_registration_id=sample_data["registration_id"],
                ),
            )
            assert attempt.id is not None
            assert attempt.status == "CREATED"
            assert attempt.decision == "PENDING"
            assert attempt.verification_method == "MANUAL"
        finally:
            db.close()

    def test_create_with_hall_ticket(self, sample_data):
        from app.schemas.identity_verification import IdentityVerificationCreate
        from app.services.identity_verification import create_attempt

        db = SessionLocal()
        try:
            attempt = create_attempt(
                db,
                IdentityVerificationCreate(
                    student_id=sample_data["student_id"],
                    exam_registration_id=sample_data["registration_id"],
                    hall_ticket_id=sample_data["hall_ticket_id"],
                ),
            )
            assert attempt.hall_ticket_id == sample_data["hall_ticket_id"]
        finally:
            db.close()

    def test_create_invalid_student(self, sample_data):
        from app.schemas.identity_verification import IdentityVerificationCreate
        from app.services.identity_verification import create_attempt

        db = SessionLocal()
        try:
            with pytest.raises(LookupError, match="not found"):
                create_attempt(
                    db,
                    IdentityVerificationCreate(
                        student_id=99999,
                        exam_registration_id=sample_data["registration_id"],
                    ),
                )
        finally:
            db.close()

    def test_create_invalid_registration(self, sample_data):
        from app.schemas.identity_verification import IdentityVerificationCreate
        from app.services.identity_verification import create_attempt

        db = SessionLocal()
        try:
            with pytest.raises(LookupError, match="not found"):
                create_attempt(
                    db,
                    IdentityVerificationCreate(
                        student_id=sample_data["student_id"],
                        exam_registration_id=99999,
                    ),
                )
        finally:
            db.close()

    def test_create_wrong_student_registration(self, sample_data):
        from app.schemas.identity_verification import IdentityVerificationCreate
        from app.services.identity_verification import create_attempt

        db = SessionLocal()
        try:
            other_student = Student(usn="IVT999", name="Other")
            db.add(other_student)
            db.commit()
            db.refresh(other_student)
            with pytest.raises(ValueError, match="belongs to student"):
                create_attempt(
                    db,
                    IdentityVerificationCreate(
                        student_id=other_student.id,
                        exam_registration_id=sample_data["registration_id"],
                    ),
                )
        finally:
            db.close()

    def test_create_wrong_hall_ticket_registration(self, sample_data):
        from app.schemas.identity_verification import IdentityVerificationCreate
        from app.services.identity_verification import create_attempt

        db = SessionLocal()
        try:
            other_student = Student(usn="IVT998", name="Other2")
            db.add(other_student)
            db.commit()
            db.refresh(other_student)
            other_reg = ExamRegistration(
                student_id=other_student.id,
                exam_id=sample_data["exam_id"],
                status=RegistrationStatus.REGISTERED.value,
            )
            db.add(other_reg)
            db.commit()
            db.refresh(other_reg)
            other_ht = HallTicket(
                exam_registration_id=other_reg.id,
                status=HallTicketStatus.CREATED.value,
            )
            db.add(other_ht)
            db.commit()
            db.refresh(other_ht)
            with pytest.raises(ValueError, match="belongs to registration"):
                create_attempt(
                    db,
                    IdentityVerificationCreate(
                        student_id=sample_data["student_id"],
                        exam_registration_id=sample_data["registration_id"],
                        hall_ticket_id=other_ht.id,
                    ),
                )
        finally:
            db.close()

    def test_create_duplicate_active(self, sample_data):
        from app.schemas.identity_verification import IdentityVerificationCreate
        from app.services.identity_verification import create_attempt

        db = SessionLocal()
        try:
            create_attempt(
                db,
                IdentityVerificationCreate(
                    student_id=sample_data["student_id"],
                    exam_registration_id=sample_data["registration_id"],
                ),
            )
            with pytest.raises(ValueError, match="already exists"):
                create_attempt(
                    db,
                    IdentityVerificationCreate(
                        student_id=sample_data["student_id"],
                        exam_registration_id=sample_data["registration_id"],
                    ),
                )
        finally:
            db.close()

    def test_create_invalid_method(self, sample_data):
        from app.schemas.identity_verification import IdentityVerificationCreate
        from app.services.identity_verification import create_attempt

        db = SessionLocal()
        try:
            with pytest.raises(ValueError, match="Invalid verification_method"):
                create_attempt(
                    db,
                    IdentityVerificationCreate(
                        student_id=sample_data["student_id"],
                        exam_registration_id=sample_data["registration_id"],
                        verification_method="INVALID",
                    ),
                )
        finally:
            db.close()


class TestServiceLifecycle:
    def _create(self, db, sample_data):
        from app.schemas.identity_verification import IdentityVerificationCreate
        from app.services.identity_verification import create_attempt
        return create_attempt(
            db,
            IdentityVerificationCreate(
                student_id=sample_data["student_id"],
                exam_registration_id=sample_data["registration_id"],
            ),
        )

    def test_start_success(self, sample_data):
        from app.services.identity_verification import start_attempt

        db = SessionLocal()
        try:
            attempt = self._create(db, sample_data)
            started = start_attempt(db, attempt.id)
            assert started.status == "IN_PROGRESS"
            assert started.started_at is not None
        finally:
            db.close()

    def test_start_not_found(self):
        from app.services.identity_verification import start_attempt

        db = SessionLocal()
        try:
            with pytest.raises(LookupError):
                start_attempt(db, 99999)
        finally:
            db.close()

    def test_start_wrong_state(self, sample_data):
        from app.services.identity_verification import start_attempt, complete_attempt

        db = SessionLocal()
        try:
            attempt = self._create(db, sample_data)
            start_attempt(db, attempt.id)
            complete_attempt(db, attempt.id, decision="MATCH")
            with pytest.raises(ValueError, match="Cannot transition"):
                start_attempt(db, attempt.id)
        finally:
            db.close()

    def test_complete_success(self, sample_data):
        from app.services.identity_verification import complete_attempt

        db = SessionLocal()
        try:
            attempt = self._create(db, sample_data)
            completed = complete_attempt(db, attempt.id, decision="MATCH")
            assert completed.status == "COMPLETED"
            assert completed.decision == "MATCH"
            assert completed.completed_at is not None
        finally:
            db.close()

    def test_complete_no_match(self, sample_data):
        from app.services.identity_verification import complete_attempt

        db = SessionLocal()
        try:
            attempt = self._create(db, sample_data)
            completed = complete_attempt(
                db, attempt.id, decision="NO_MATCH",
                failure_reason="Similarity too low",
            )
            assert completed.decision == "NO_MATCH"
            assert completed.failure_reason == "Similarity too low"
        finally:
            db.close()

    def test_complete_inconclusive(self, sample_data):
        from app.services.identity_verification import complete_attempt

        db = SessionLocal()
        try:
            attempt = self._create(db, sample_data)
            completed = complete_attempt(db, attempt.id, decision="INCONCLUSIVE")
            assert completed.decision == "INCONCLUSIVE"
        finally:
            db.close()

    def test_complete_invalid_decision(self, sample_data):
        from app.services.identity_verification import complete_attempt

        db = SessionLocal()
        try:
            attempt = self._create(db, sample_data)
            with pytest.raises(ValueError, match="Invalid decision"):
                complete_attempt(db, attempt.id, decision="BOGUS")
        finally:
            db.close()

    def test_complete_terminal_state(self, sample_data):
        from app.services.identity_verification import complete_attempt

        db = SessionLocal()
        try:
            attempt = self._create(db, sample_data)
            complete_attempt(db, attempt.id, decision="MATCH")
            with pytest.raises(ValueError, match="Cannot transition"):
                complete_attempt(db, attempt.id, decision="NO_MATCH")
        finally:
            db.close()

    def test_fail_success(self, sample_data):
        from app.services.identity_verification import fail_attempt

        db = SessionLocal()
        try:
            attempt = self._create(db, sample_data)
            failed = fail_attempt(db, attempt.id, reason="Provider error")
            assert failed.status == "FAILED"
            assert failed.failure_reason == "Provider error"
        finally:
            db.close()

    def test_fail_terminal_state(self, sample_data):
        from app.services.identity_verification import fail_attempt

        db = SessionLocal()
        try:
            attempt = self._create(db, sample_data)
            fail_attempt(db, attempt.id, reason="error")
            with pytest.raises(ValueError, match="Cannot transition"):
                fail_attempt(db, attempt.id, reason="another error")
        finally:
            db.close()

    def test_cancel_success(self, sample_data):
        from app.services.identity_verification import cancel_attempt

        db = SessionLocal()
        try:
            attempt = self._create(db, sample_data)
            cancelled = cancel_attempt(db, attempt.id, reason="changed mind")
            assert cancelled.status == "CANCELLED"
            assert cancelled.failure_reason == "changed mind"
        finally:
            db.close()

    def test_cancel_terminal_state(self, sample_data):
        from app.services.identity_verification import cancel_attempt

        db = SessionLocal()
        try:
            attempt = self._create(db, sample_data)
            cancel_attempt(db, attempt.id)
            with pytest.raises(ValueError, match="Cannot transition"):
                cancel_attempt(db, attempt.id)
        finally:
            db.close()


class TestServiceEvidence:
    def _create_and_start(self, db, sample_data):
        from app.schemas.identity_verification import IdentityVerificationCreate
        from app.services.identity_verification import create_attempt, start_attempt
        attempt = create_attempt(
            db,
            IdentityVerificationCreate(
                student_id=sample_data["student_id"],
                exam_registration_id=sample_data["registration_id"],
            ),
        )
        return start_attempt(db, attempt.id)

    def test_record_evidence_success(self, sample_data):
        from app.schemas.identity_verification import IdentityVerificationEvidenceCreate
        from app.services.identity_verification import record_evidence

        db = SessionLocal()
        try:
            attempt = self._create_and_start(db, sample_data)
            ev = record_evidence(
                db,
                attempt.id,
                IdentityVerificationEvidenceCreate(
                    signal_type="similarity_score",
                    signal_value="0.92",
                    provider_name="test_provider",
                    confidence=0.92,
                ),
            )
            assert ev.id is not None
            assert ev.signal_type == "similarity_score"
            assert ev.attempt_id == attempt.id
        finally:
            db.close()

    def test_record_evidence_not_found(self):
        from app.schemas.identity_verification import IdentityVerificationEvidenceCreate
        from app.services.identity_verification import record_evidence

        db = SessionLocal()
        try:
            with pytest.raises(LookupError):
                record_evidence(
                    db,
                    99999,
                    IdentityVerificationEvidenceCreate(
                        signal_type="similarity_score",
                        signal_value="0.92",
                    ),
                )
        finally:
            db.close()

    def test_record_evidence_terminal_state(self, sample_data):
        from app.schemas.identity_verification import IdentityVerificationEvidenceCreate
        from app.services.identity_verification import (
            record_evidence, complete_attempt,
        )

        db = SessionLocal()
        try:
            attempt = self._create_and_start(db, sample_data)
            complete_attempt(db, attempt.id, decision="MATCH")
            with pytest.raises(ValueError, match="Cannot record evidence"):
                record_evidence(
                    db,
                    attempt.id,
                    IdentityVerificationEvidenceCreate(
                        signal_type="similarity_score",
                        signal_value="0.92",
                    ),
                )
        finally:
            db.close()

    def test_record_evidence_on_created_status(self, sample_data):
        from app.schemas.identity_verification import (
            IdentityVerificationCreate,
            IdentityVerificationEvidenceCreate,
        )
        from app.services.identity_verification import (
            create_attempt, record_evidence,
        )

        db = SessionLocal()
        try:
            attempt = create_attempt(
                db,
                IdentityVerificationCreate(
                    student_id=sample_data["student_id"],
                    exam_registration_id=sample_data["registration_id"],
                ),
            )
            ev = record_evidence(
                db,
                attempt.id,
                IdentityVerificationEvidenceCreate(
                    signal_type="liveness",
                    signal_value="PASS",
                ),
            )
            assert ev.signal_type == "liveness"
        finally:
            db.close()


class TestServiceContext:
    def test_get_context(self, sample_data):
        from app.schemas.identity_verification import IdentityVerificationCreate
        from app.services.identity_verification import (
            create_attempt, get_attempt_with_context,
        )

        db = SessionLocal()
        try:
            attempt = create_attempt(
                db,
                IdentityVerificationCreate(
                    student_id=sample_data["student_id"],
                    exam_registration_id=sample_data["registration_id"],
                    hall_ticket_id=sample_data["hall_ticket_id"],
                ),
            )
            ctx = get_attempt_with_context(db, attempt.id)
            assert ctx is not None
            assert ctx["student"].usn == "IVT001"
            assert ctx["exam"] is not None
            assert ctx["hall_ticket"] is not None
            assert ctx["hall_ticket"].id == sample_data["hall_ticket_id"]
        finally:
            db.close()

    def test_get_context_not_found(self):
        from app.services.identity_verification import get_attempt_with_context

        db = SessionLocal()
        try:
            ctx = get_attempt_with_context(db, 99999)
            assert ctx is None
        finally:
            db.close()


class TestServiceList:
    def test_list_empty(self):
        from app.services.identity_verification import list_attempts

        db = SessionLocal()
        try:
            result = list_attempts(db)
            assert result["total"] == 0
            assert result["items"] == []
        finally:
            db.close()

    def test_list_with_data(self, sample_data):
        from app.schemas.identity_verification import IdentityVerificationCreate
        from app.services.identity_verification import create_attempt, list_attempts

        db = SessionLocal()
        try:
            create_attempt(
                db,
                IdentityVerificationCreate(
                    student_id=sample_data["student_id"],
                    exam_registration_id=sample_data["registration_id"],
                ),
            )
            result = list_attempts(db)
            assert result["total"] == 1
        finally:
            db.close()

    def test_list_filter_status(self, sample_data):
        from app.schemas.identity_verification import IdentityVerificationCreate
        from app.services.identity_verification import create_attempt, list_attempts

        db = SessionLocal()
        try:
            create_attempt(
                db,
                IdentityVerificationCreate(
                    student_id=sample_data["student_id"],
                    exam_registration_id=sample_data["registration_id"],
                ),
            )
            result = list_attempts(db, status="CREATED")
            assert result["total"] == 1
            result = list_attempts(db, status="COMPLETED")
            assert result["total"] == 0
        finally:
            db.close()

    def test_list_filter_student(self, sample_data):
        from app.schemas.identity_verification import IdentityVerificationCreate
        from app.services.identity_verification import create_attempt, list_attempts

        db = SessionLocal()
        try:
            create_attempt(
                db,
                IdentityVerificationCreate(
                    student_id=sample_data["student_id"],
                    exam_registration_id=sample_data["registration_id"],
                ),
            )
            result = list_attempts(db, student_id=sample_data["student_id"])
            assert result["total"] == 1
            result = list_attempts(db, student_id=99999)
            assert result["total"] == 0
        finally:
            db.close()


class TestDecisionEngine:
    def test_no_evidence(self):
        from app.services.identity_verification_decision import evaluate_evidence
        decision, reasoning = evaluate_evidence([])
        assert decision == "INCONCLUSIVE"
        assert "No evidence" in reasoning

    def test_high_similarity_match(self):
        from app.services.identity_verification_decision import evaluate_evidence
        from app.models.identity_verification import IdentityVerificationEvidence

        evidence = [
            IdentityVerificationEvidence(
                signal_type="similarity_score",
                signal_value="0.95",
                confidence=0.95,
            ),
        ]
        decision, reasoning = evaluate_evidence(evidence)
        assert decision == "MATCH"
        assert "0.950" in reasoning

    def test_low_similarity_no_match(self):
        from app.services.identity_verification_decision import evaluate_evidence
        from app.models.identity_verification import IdentityVerificationEvidence

        evidence = [
            IdentityVerificationEvidence(
                signal_type="similarity_score",
                signal_value="0.45",
                confidence=0.45,
            ),
        ]
        decision, reasoning = evaluate_evidence(evidence)
        assert decision == "NO_MATCH"
        assert "0.450" in reasoning

    def test_near_threshold_inconclusive(self):
        from app.services.identity_verification_decision import evaluate_evidence
        from app.models.identity_verification import IdentityVerificationEvidence

        evidence = [
            IdentityVerificationEvidence(
                signal_type="similarity_score",
                signal_value="0.65",
                confidence=0.65,
            ),
        ]
        decision, reasoning = evaluate_evidence(evidence)
        assert decision == "INCONCLUSIVE"
        assert "near threshold" in reasoning

    def test_liveness_failure(self):
        from app.services.identity_verification_decision import evaluate_evidence
        from app.models.identity_verification import IdentityVerificationEvidence

        evidence = [
            IdentityVerificationEvidence(
                signal_type="similarity_score",
                signal_value="0.95",
                confidence=0.95,
            ),
            IdentityVerificationEvidence(
                signal_type="liveness",
                signal_value="FAIL",
            ),
        ]
        decision, reasoning = evaluate_evidence(evidence)
        assert decision == "NO_MATCH"
        assert "Liveness check failed" in reasoning

    def test_quality_issue_with_high_similarity(self):
        from app.services.identity_verification_decision import evaluate_evidence
        from app.models.identity_verification import IdentityVerificationEvidence

        evidence = [
            IdentityVerificationEvidence(
                signal_type="similarity_score",
                signal_value="0.92",
                confidence=0.92,
            ),
            IdentityVerificationEvidence(
                signal_type="image_quality",
                signal_value="POOR",
            ),
        ]
        decision, reasoning = evaluate_evidence(evidence)
        assert decision == "INCONCLUSIVE"
        assert "quality is degraded" in reasoning

    def test_liveness_pass_no_similarity(self):
        from app.services.identity_verification_decision import evaluate_evidence
        from app.models.identity_verification import IdentityVerificationEvidence

        evidence = [
            IdentityVerificationEvidence(
                signal_type="liveness",
                signal_value="PASS",
            ),
        ]
        decision, reasoning = evaluate_evidence(evidence)
        assert decision == "INCONCLUSIVE"
        assert "no similarity score" in reasoning


class TestApiCreate:
    def test_api_create(self, client, sample_data):
        response = client.post(
            "/api/v1/identity-verifications",
            json={
                "student_id": sample_data["student_id"],
                "exam_registration_id": sample_data["registration_id"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "CREATED"
        assert data["decision"] == "PENDING"
        assert data["student_id"] == sample_data["student_id"]

    def test_api_create_with_hall_ticket(self, client, sample_data):
        response = client.post(
            "/api/v1/identity-verifications",
            json={
                "student_id": sample_data["student_id"],
                "exam_registration_id": sample_data["registration_id"],
                "hall_ticket_id": sample_data["hall_ticket_id"],
            },
        )
        assert response.status_code == 201
        assert response.json()["hall_ticket_id"] == sample_data["hall_ticket_id"]

    def test_api_create_invalid_student(self, client, sample_data):
        response = client.post(
            "/api/v1/identity-verifications",
            json={
                "student_id": 99999,
                "exam_registration_id": sample_data["registration_id"],
            },
        )
        assert response.status_code == 404

    def test_api_create_missing_body(self, client):
        response = client.post("/api/v1/identity-verifications", json={})
        assert response.status_code == 422


class TestApiGet:
    def test_api_get(self, client, sample_data):
        create_resp = client.post(
            "/api/v1/identity-verifications",
            json={
                "student_id": sample_data["student_id"],
                "exam_registration_id": sample_data["registration_id"],
            },
        )
        iv_id = create_resp.json()["id"]
        response = client.get(f"/api/v1/identity-verifications/{iv_id}")
        assert response.status_code == 200
        assert response.json()["attempt"]["id"] == iv_id
        assert response.json()["evidence"] == []

    def test_api_get_not_found(self, client):
        response = client.get("/api/v1/identity-verifications/99999")
        assert response.status_code == 404

    def test_api_get_context(self, client, sample_data):
        create_resp = client.post(
            "/api/v1/identity-verifications",
            json={
                "student_id": sample_data["student_id"],
                "exam_registration_id": sample_data["registration_id"],
                "hall_ticket_id": sample_data["hall_ticket_id"],
            },
        )
        iv_id = create_resp.json()["id"]
        response = client.get(f"/api/v1/identity-verifications/{iv_id}/context")
        assert response.status_code == 200
        data = response.json()
        assert data["student"]["usn"] == "IVT001"
        assert data["exam"] is not None


class TestApiLifecycle:
    def test_api_full_lifecycle(self, client, sample_data):
        create_resp = client.post(
            "/api/v1/identity-verifications",
            json={
                "student_id": sample_data["student_id"],
                "exam_registration_id": sample_data["registration_id"],
            },
        )
        iv_id = create_resp.json()["id"]

        start_resp = client.post(f"/api/v1/identity-verifications/{iv_id}/start")
        assert start_resp.status_code == 200
        assert start_resp.json()["status"] == "IN_PROGRESS"

        ev_resp = client.post(
            f"/api/v1/identity-verifications/{iv_id}/evidence",
            json={
                "signal_type": "similarity_score",
                "signal_value": "0.92",
                "confidence": 0.92,
                "provider_name": "test",
            },
        )
        assert ev_resp.status_code == 201

        complete_resp = client.post(
            f"/api/v1/identity-verifications/{iv_id}/complete",
            json={"decision": "MATCH"},
        )
        assert complete_resp.status_code == 200
        assert complete_resp.json()["status"] == "COMPLETED"
        assert complete_resp.json()["decision"] == "MATCH"

    def test_api_fail(self, client, sample_data):
        create_resp = client.post(
            "/api/v1/identity-verifications",
            json={
                "student_id": sample_data["student_id"],
                "exam_registration_id": sample_data["registration_id"],
            },
        )
        iv_id = create_resp.json()["id"]

        fail_resp = client.post(
            f"/api/v1/identity-verifications/{iv_id}/fail",
            json={"reason": "Provider timeout"},
        )
        assert fail_resp.status_code == 200
        assert fail_resp.json()["status"] == "FAILED"

    def test_api_cancel(self, client, sample_data):
        create_resp = client.post(
            "/api/v1/identity-verifications",
            json={
                "student_id": sample_data["student_id"],
                "exam_registration_id": sample_data["registration_id"],
            },
        )
        iv_id = create_resp.json()["id"]

        cancel_resp = client.post(
            f"/api/v1/identity-verifications/{iv_id}/cancel",
            json={"reason": "Not needed"},
        )
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "CANCELLED"

    def test_api_evaluate(self, client, sample_data):
        create_resp = client.post(
            "/api/v1/identity-verifications",
            json={
                "student_id": sample_data["student_id"],
                "exam_registration_id": sample_data["registration_id"],
            },
        )
        iv_id = create_resp.json()["id"]

        client.post(f"/api/v1/identity-verifications/{iv_id}/start")

        client.post(
            f"/api/v1/identity-verifications/{iv_id}/evidence",
            json={
                "signal_type": "similarity_score",
                "signal_value": "0.92",
                "confidence": 0.92,
            },
        )

        eval_resp = client.post(f"/api/v1/identity-verifications/{iv_id}/evaluate")
        assert eval_resp.status_code == 200
        assert eval_resp.json()["status"] == "COMPLETED"
        assert eval_resp.json()["decision"] == "MATCH"

    def test_api_duplicate_active(self, client, sample_data):
        client.post(
            "/api/v1/identity-verifications",
            json={
                "student_id": sample_data["student_id"],
                "exam_registration_id": sample_data["registration_id"],
            },
        )
        response = client.post(
            "/api/v1/identity-verifications",
            json={
                "student_id": sample_data["student_id"],
                "exam_registration_id": sample_data["registration_id"],
            },
        )
        assert response.status_code == 422


class TestApiList:
    def test_api_list(self, client, sample_data):
        client.post(
            "/api/v1/identity-verifications",
            json={
                "student_id": sample_data["student_id"],
                "exam_registration_id": sample_data["registration_id"],
            },
        )
        response = client.get("/api/v1/identity-verifications")
        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_api_list_filter_status(self, client, sample_data):
        client.post(
            "/api/v1/identity-verifications",
            json={
                "student_id": sample_data["student_id"],
                "exam_registration_id": sample_data["registration_id"],
            },
        )
        response = client.get("/api/v1/identity-verifications?status=CREATED")
        assert response.json()["total"] == 1
        response = client.get("/api/v1/identity-verifications?status=COMPLETED")
        assert response.json()["total"] == 0

    def test_api_list_filter_student(self, client, sample_data):
        client.post(
            "/api/v1/identity-verifications",
            json={
                "student_id": sample_data["student_id"],
                "exam_registration_id": sample_data["registration_id"],
            },
        )
        response = client.get(
            f"/api/v1/identity-verifications?student_id={sample_data['student_id']}"
        )
        assert response.json()["total"] == 1

    def test_api_list_empty(self, client):
        response = client.get("/api/v1/identity-verifications")
        assert response.status_code == 200
        assert response.json()["items"] == []


class TestRegression:
    def test_existing_tests_unaffected(self, client):
        response = client.get("/api/v1/students?page=1&page_size=1")
        assert response.status_code == 200

    def test_hall_tickets_still_work(self, client, sample_data):
        response = client.get("/api/v1/hall-tickets")
        assert response.status_code == 200

    def test_verification_still_works(self, client):
        response = client.get("/api/v1/ping")
        assert response.status_code == 200
