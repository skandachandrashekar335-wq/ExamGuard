"""Phase 11.1 — Anti-Proxy Domain & Database Foundation.

Tests for SecuritySignal and ProxyRiskAssessment models and associated enums.
Covers: creation, defaults, FK relationships, nullable fields, timestamps,
enum persistence, model registration, and historical-record safety.
"""

import pytest
from datetime import date, time
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Base
from app.models.camera import Camera
from app.models.entry_point import EntryPoint
from app.models.entry_verification import (
    EntryVerification,
    EntryVerificationStatus,
)
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration
from app.models.hall_ticket import HallTicket, HallTicketStatus
from app.models.proxy_risk import (
    ProxyRiskAssessment,
    RiskLevel,
    SecuritySignal,
    SecuritySignalType,
    SignalStrength,
    SIGNAL_STRENGTH_DEFAULTS,
)
from app.models.student import Student
from app.models.subject import Subject


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture()
def student(db):
    s = Student(usn="TEST001", name="Test Student")
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@pytest.fixture()
def subject(db):
    s = Subject(code="SUB101", name="Test Subject", department="CS", semester=6)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@pytest.fixture()
def exam(db, subject):
    e = Exam(
        subject_id=subject.id,
        exam_name="Test Exam",
        exam_date=date(2026, 9, 15),
        start_time=time(9, 0),
        end_time=time(12, 0),
        semester=6,
        department="CS",
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


@pytest.fixture()
def hall(db):
    h = ExamHall(building="TestBuilding", room_number="101", capacity=50)
    db.add(h)
    db.commit()
    db.refresh(h)
    return h


@pytest.fixture()
def registration(db, student, exam):
    r = ExamRegistration(student_id=student.id, exam_id=exam.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@pytest.fixture()
def entry_point(db, hall):
    ep = EntryPoint(name="Main Gate", code="MAIN_GATE", exam_hall_id=hall.id)
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


@pytest.fixture()
def camera(db, hall):
    c = Camera(
        name="Test Camera",
        device_identifier="CAM-TEST-001",
        exam_hall_id=hall.id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture()
def entry_verification(db, student, registration, hall, entry_point):
    ev = EntryVerification(
        student_id=student.id,
        exam_registration_id=registration.id,
        exam_hall_id=hall.id,
        entry_point_id=entry_point.id,
        status=EntryVerificationStatus.IN_PROGRESS.value,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


@pytest.fixture()
def hall_ticket(db, registration):
    ht = HallTicket(
        exam_registration_id=registration.id,
        status=HallTicketStatus.VERIFIED.value,
    )
    db.add(ht)
    db.commit()
    db.refresh(ht)
    return ht


# ---------------------------------------------------------------------------
# Enum Tests — SecuritySignalType
# ---------------------------------------------------------------------------

class TestSecuritySignalTypeEnum:
    def test_has_required_values(self):
        assert SecuritySignalType.DUPLICATE_ENTRY.value == "DUPLICATE_ENTRY"
        assert SecuritySignalType.UNUSUAL_ENTRY_POINT.value == "UNUSUAL_ENTRY_POINT"
        assert SecuritySignalType.UNUSUAL_TIME.value == "UNUSUAL_TIME"
        assert SecuritySignalType.SEAT_MISMATCH.value == "SEAT_MISMATCH"
        assert SecuritySignalType.MULTIPLE_REGISTRATIONS.value == "MULTIPLE_REGISTRATIONS"
        assert SecuritySignalType.RAPID_ENTRY.value == "RAPID_ENTRY"
        assert SecuritySignalType.DOCUMENT_ANOMALY.value == "DOCUMENT_ANOMALY"
        assert SecuritySignalType.BEHAVIORAL_ANOMALY.value == "BEHAVIORAL_ANOMALY"
        assert SecuritySignalType.IDENTITY_MISMATCH.value == "IDENTITY_MISMATCH"
        assert SecuritySignalType.MANUAL_FLAG.value == "MANUAL_FLAG"

    def test_string_enum(self):
        assert isinstance(SecuritySignalType.DUPLICATE_ENTRY, str)
        assert SecuritySignalType.DUPLICATE_ENTRY == "DUPLICATE_ENTRY"

    def test_all_values_unique(self):
        values = [e.value for e in SecuritySignalType]
        assert len(values) == len(set(values))

    def test_has_ten_signal_types(self):
        assert len(SecuritySignalType) == 10


# ---------------------------------------------------------------------------
# Enum Tests — SignalStrength
# ---------------------------------------------------------------------------

class TestSignalStrengthEnum:
    def test_has_required_values(self):
        assert SignalStrength.STRONG.value == "STRONG"
        assert SignalStrength.MODERATE.value == "MODERATE"
        assert SignalStrength.WEAK.value == "WEAK"
        assert SignalStrength.INFORMATIONAL.value == "INFORMATIONAL"

    def test_string_enum(self):
        assert isinstance(SignalStrength.STRONG, str)
        assert SignalStrength.STRONG == "STRONG"

    def test_all_values_unique(self):
        values = [e.value for e in SignalStrength]
        assert len(values) == len(set(values))


# ---------------------------------------------------------------------------
# Enum Tests — RiskLevel
# ---------------------------------------------------------------------------

class TestRiskLevelEnum:
    def test_has_required_values(self):
        assert RiskLevel.LOW.value == "LOW"
        assert RiskLevel.ELEVATED.value == "ELEVATED"
        assert RiskLevel.HIGH.value == "HIGH"
        assert RiskLevel.CRITICAL.value == "CRITICAL"

    def test_string_enum(self):
        assert isinstance(RiskLevel.LOW, str)
        assert RiskLevel.LOW == "LOW"

    def test_all_values_unique(self):
        values = [e.value for e in RiskLevel]
        assert len(values) == len(set(values))

    def test_has_four_levels(self):
        assert len(RiskLevel) == 4


# ---------------------------------------------------------------------------
# Signal Strength Defaults
# ---------------------------------------------------------------------------

class TestSignalStrengthDefaults:
    def test_has_entry_for_each_signal_type(self):
        for sig_type in SecuritySignalType:
            assert sig_type.value in SIGNAL_STRENGTH_DEFAULTS

    def test_expected_defaults(self):
        assert SIGNAL_STRENGTH_DEFAULTS["DUPLICATE_ENTRY"] == SignalStrength.MODERATE
        assert SIGNAL_STRENGTH_DEFAULTS["UNUSUAL_ENTRY_POINT"] == SignalStrength.WEAK
        assert SIGNAL_STRENGTH_DEFAULTS["UNUSUAL_TIME"] == SignalStrength.WEAK
        assert SIGNAL_STRENGTH_DEFAULTS["SEAT_MISMATCH"] == SignalStrength.STRONG
        assert SIGNAL_STRENGTH_DEFAULTS["MULTIPLE_REGISTRATIONS"] == SignalStrength.STRONG
        assert SIGNAL_STRENGTH_DEFAULTS["RAPID_ENTRY"] == SignalStrength.MODERATE
        assert SIGNAL_STRENGTH_DEFAULTS["DOCUMENT_ANOMALY"] == SignalStrength.STRONG
        assert SIGNAL_STRENGTH_DEFAULTS["BEHAVIORAL_ANOMALY"] == SignalStrength.MODERATE
        assert SIGNAL_STRENGTH_DEFAULTS["IDENTITY_MISMATCH"] == SignalStrength.STRONG
        assert SIGNAL_STRENGTH_DEFAULTS["MANUAL_FLAG"] == SignalStrength.MODERATE

    def test_all_defaults_are_valid_signal_strengths(self):
        for sig_type, strength in SIGNAL_STRENGTH_DEFAULTS.items():
            assert isinstance(strength, SignalStrength), f"{sig_type} default is not a valid SignalStrength"


# ---------------------------------------------------------------------------
# SecuritySignal — Creation & Defaults
# ---------------------------------------------------------------------------

class TestSecuritySignalCreation:
    def test_create_minimal(self, db, entry_verification):
        sig = SecuritySignal(
            entry_verification_id=entry_verification.id,
            signal_type=SecuritySignalType.DUPLICATE_ENTRY.value,
            strength=SignalStrength.MODERATE.value,
            source="hall_ticket_check",
        )
        db.add(sig)
        db.commit()
        db.refresh(sig)

        assert sig.id is not None
        assert sig.entry_verification_id == entry_verification.id
        assert sig.signal_type == SecuritySignalType.DUPLICATE_ENTRY.value
        assert sig.strength == SignalStrength.MODERATE.value
        assert sig.source == "hall_ticket_check"

    def test_nullable_fields_default_none(self, db, entry_verification):
        sig = SecuritySignal(
            entry_verification_id=entry_verification.id,
            signal_type=SecuritySignalType.DUPLICATE_ENTRY.value,
            strength=SignalStrength.MODERATE.value,
            source="hall_ticket_check",
        )
        db.add(sig)
        db.commit()
        db.refresh(sig)

        assert sig.description is None
        assert sig.evidence_json is None

    def test_created_at_auto_populated(self, db, entry_verification):
        sig = SecuritySignal(
            entry_verification_id=entry_verification.id,
            signal_type=SecuritySignalType.DUPLICATE_ENTRY.value,
            strength=SignalStrength.MODERATE.value,
            source="hall_ticket_check",
        )
        db.add(sig)
        db.commit()
        db.refresh(sig)

        assert sig.created_at is not None

    def test_with_all_optionals(self, db, entry_verification):
        sig = SecuritySignal(
            entry_verification_id=entry_verification.id,
            signal_type=SecuritySignalType.IDENTITY_MISMATCH.value,
            strength=SignalStrength.STRONG.value,
            source="identity_check",
            description="Face mismatch detected",
            evidence_json='{"face_similarity": 0.42}',
        )
        db.add(sig)
        db.commit()
        db.refresh(sig)

        assert sig.description == "Face mismatch detected"
        assert sig.evidence_json == '{"face_similarity": 0.42}'

    def test_all_signal_types_persist(self, db, entry_verification):
        for sig_type in SecuritySignalType:
            sig = SecuritySignal(
                entry_verification_id=entry_verification.id,
                signal_type=sig_type.value,
                strength=SignalStrength.WEAK.value,
                source="test",
            )
            db.add(sig)
            db.commit()
            db.refresh(sig)
            assert sig.signal_type == sig_type.value

    def test_all_strength_values_persist(self, db, entry_verification):
        for strength in SignalStrength:
            sig = SecuritySignal(
                entry_verification_id=entry_verification.id,
                signal_type=SecuritySignalType.DUPLICATE_ENTRY.value,
                strength=strength.value,
                source="test",
            )
            db.add(sig)
            db.commit()
            db.refresh(sig)
            assert sig.strength == strength.value


# ---------------------------------------------------------------------------
# SecuritySignal — Repr
# ---------------------------------------------------------------------------

class TestSecuritySignalRepr:
    def test_repr(self, db, entry_verification):
        sig = SecuritySignal(
            entry_verification_id=entry_verification.id,
            signal_type=SecuritySignalType.DUPLICATE_ENTRY.value,
            strength=SignalStrength.MODERATE.value,
            source="hall_ticket_check",
        )
        db.add(sig)
        db.commit()
        db.refresh(sig)

        r = repr(sig)
        assert "SecuritySignal" in r
        assert f"id={sig.id}" in r
        assert f"entry_verification_id={entry_verification.id}" in r
        assert "DUPLICATE_ENTRY" in r
        assert "MODERATE" in r


# ---------------------------------------------------------------------------
# SecuritySignal — Relationship
# ---------------------------------------------------------------------------

class TestSecuritySignalRelationship:
    def test_entry_verification_relationship_loads(self, db, entry_verification):
        sig = SecuritySignal(
            entry_verification_id=entry_verification.id,
            signal_type=SecuritySignalType.DUPLICATE_ENTRY.value,
            strength=SignalStrength.MODERATE.value,
            source="hall_ticket_check",
        )
        db.add(sig)
        db.commit()
        db.refresh(sig)

        loaded = db.get(SecuritySignal, sig.id)
        assert loaded.entry_verification.id == entry_verification.id


# ---------------------------------------------------------------------------
# SecuritySignal — Data Integrity
# ---------------------------------------------------------------------------

class TestSecuritySignalDataIntegrity:
    def test_missing_entry_verification_id_raises(self, db):
        sig = SecuritySignal(
            signal_type=SecuritySignalType.DUPLICATE_ENTRY.value,
            strength=SignalStrength.MODERATE.value,
            source="hall_ticket_check",
        )
        db.add(sig)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_missing_signal_type_raises(self, db, entry_verification):
        sig = SecuritySignal(
            entry_verification_id=entry_verification.id,
            strength=SignalStrength.MODERATE.value,
            source="hall_ticket_check",
        )
        db.add(sig)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_missing_strength_raises(self, db, entry_verification):
        sig = SecuritySignal(
            entry_verification_id=entry_verification.id,
            signal_type=SecuritySignalType.DUPLICATE_ENTRY.value,
            source="hall_ticket_check",
        )
        db.add(sig)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_missing_source_raises(self, db, entry_verification):
        sig = SecuritySignal(
            entry_verification_id=entry_verification.id,
            signal_type=SecuritySignalType.DUPLICATE_ENTRY.value,
            strength=SignalStrength.MODERATE.value,
        )
        db.add(sig)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


# ---------------------------------------------------------------------------
# ProxyRiskAssessment — Creation & Defaults
# ---------------------------------------------------------------------------

class TestProxyRiskAssessmentCreation:
    def test_create_minimal(self, db, entry_verification):
        pra = ProxyRiskAssessment(
            entry_verification_id=entry_verification.id,
            risk_level=RiskLevel.LOW.value,
            risk_score=10.0,
        )
        db.add(pra)
        db.commit()
        db.refresh(pra)

        assert pra.id is not None
        assert pra.entry_verification_id == entry_verification.id
        assert pra.risk_level == RiskLevel.LOW.value
        assert pra.risk_score == 10.0

    def test_nullable_fields_default_none(self, db, entry_verification):
        pra = ProxyRiskAssessment(
            entry_verification_id=entry_verification.id,
            risk_level=RiskLevel.LOW.value,
            risk_score=10.0,
        )
        db.add(pra)
        db.commit()
        db.refresh(pra)

        assert pra.signals_summary_json is None
        assert pra.policy_version is None

    def test_assessed_at_auto_populated(self, db, entry_verification):
        pra = ProxyRiskAssessment(
            entry_verification_id=entry_verification.id,
            risk_level=RiskLevel.LOW.value,
            risk_score=10.0,
        )
        db.add(pra)
        db.commit()
        db.refresh(pra)

        assert pra.assessed_at is not None

    def test_with_all_optionals(self, db, entry_verification):
        pra = ProxyRiskAssessment(
            entry_verification_id=entry_verification.id,
            risk_level=RiskLevel.HIGH.value,
            risk_score=72.5,
            signals_summary_json='{"signal_count": 3}',
            policy_version="1.0",
        )
        db.add(pra)
        db.commit()
        db.refresh(pra)

        assert pra.signals_summary_json == '{"signal_count": 3}'
        assert pra.policy_version == "1.0"

    def test_all_risk_levels_persist(self, db, entry_verification):
        for level in RiskLevel:
            pra = ProxyRiskAssessment(
                entry_verification_id=entry_verification.id,
                risk_level=level.value,
                risk_score=0.0,
            )
            db.add(pra)
            db.commit()
            db.refresh(pra)
            assert pra.risk_level == level.value

    def test_multiple_assessments_for_same_verification(self, db, entry_verification):
        pra1 = ProxyRiskAssessment(
            entry_verification_id=entry_verification.id,
            risk_level=RiskLevel.LOW.value,
            risk_score=10.0,
        )
        pra2 = ProxyRiskAssessment(
            entry_verification_id=entry_verification.id,
            risk_level=RiskLevel.HIGH.value,
            risk_score=70.0,
        )
        db.add(pra1)
        db.commit()
        db.refresh(pra1)

        db.add(pra2)
        db.commit()
        db.refresh(pra2)

        assert pra1.id != pra2.id

    def test_risk_score_as_float(self, db, entry_verification):
        pra = ProxyRiskAssessment(
            entry_verification_id=entry_verification.id,
            risk_level=RiskLevel.ELEVATED.value,
            risk_score=45.75,
        )
        db.add(pra)
        db.commit()
        db.refresh(pra)

        assert pra.risk_score == pytest.approx(45.75)


# ---------------------------------------------------------------------------
# ProxyRiskAssessment — Repr
# ---------------------------------------------------------------------------

class TestProxyRiskAssessmentRepr:
    def test_repr(self, db, entry_verification):
        pra = ProxyRiskAssessment(
            entry_verification_id=entry_verification.id,
            risk_level=RiskLevel.HIGH.value,
            risk_score=72.5,
        )
        db.add(pra)
        db.commit()
        db.refresh(pra)

        r = repr(pra)
        assert "ProxyRiskAssessment" in r
        assert f"id={pra.id}" in r
        assert f"entry_verification_id={entry_verification.id}" in r
        assert "HIGH" in r
        assert "72.5" in r


# ---------------------------------------------------------------------------
# ProxyRiskAssessment — Relationship
# ---------------------------------------------------------------------------

class TestProxyRiskAssessmentRelationship:
    def test_entry_verification_relationship_loads(self, db, entry_verification):
        pra = ProxyRiskAssessment(
            entry_verification_id=entry_verification.id,
            risk_level=RiskLevel.LOW.value,
            risk_score=10.0,
        )
        db.add(pra)
        db.commit()
        db.refresh(pra)

        loaded = db.get(ProxyRiskAssessment, pra.id)
        assert loaded.entry_verification.id == entry_verification.id


# ---------------------------------------------------------------------------
# ProxyRiskAssessment — Data Integrity
# ---------------------------------------------------------------------------

class TestProxyRiskAssessmentDataIntegrity:
    def test_missing_entry_verification_id_raises(self, db):
        pra = ProxyRiskAssessment(
            risk_level=RiskLevel.LOW.value,
            risk_score=10.0,
        )
        db.add(pra)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_missing_risk_level_raises(self, db, entry_verification):
        pra = ProxyRiskAssessment(
            entry_verification_id=entry_verification.id,
            risk_score=10.0,
        )
        db.add(pra)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_missing_risk_score_raises(self, db, entry_verification):
        pra = ProxyRiskAssessment(
            entry_verification_id=entry_verification.id,
            risk_level=RiskLevel.LOW.value,
        )
        db.add(pra)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


# ---------------------------------------------------------------------------
# Model Registration & Table Introspection
# ---------------------------------------------------------------------------

class TestModelRegistration:
    def test_security_signals_table_exists(self):
        assert "security_signals" in Base.metadata.tables

    def test_proxy_risk_assessments_table_exists(self):
        assert "proxy_risk_assessments" in Base.metadata.tables

    def test_security_signals_expected_columns(self):
        table = Base.metadata.tables["security_signals"]
        column_names = {c.name for c in table.columns}
        expected = {
            "id",
            "entry_verification_id",
            "signal_type",
            "strength",
            "source",
            "description",
            "evidence_json",
            "created_at",
        }
        assert expected == column_names

    def test_proxy_risk_assessments_expected_columns(self):
        table = Base.metadata.tables["proxy_risk_assessments"]
        column_names = {c.name for c in table.columns}
        expected = {
            "id",
            "entry_verification_id",
            "risk_level",
            "risk_score",
            "signals_summary_json",
            "assessed_at",
            "policy_version",
        }
        assert expected == column_names

    def test_security_signals_foreign_keys(self):
        table = Base.metadata.tables["security_signals"]
        fk_parent_columns = {fk.parent.name for fk in table.foreign_keys}
        assert "entry_verification_id" in fk_parent_columns

    def test_proxy_risk_assessments_foreign_keys(self):
        table = Base.metadata.tables["proxy_risk_assessments"]
        fk_parent_columns = {fk.parent.name for fk in table.foreign_keys}
        assert "entry_verification_id" in fk_parent_columns

    def test_no_cascade_delete_on_security_signals(self):
        table = Base.metadata.tables["security_signals"]
        fk = [fk for fk in table.foreign_keys if fk.parent.name == "entry_verification_id"][0]
        assert fk.ondelete is None or fk.ondelete != "CASCADE"

    def test_no_cascade_delete_on_proxy_risk_assessments(self):
        table = Base.metadata.tables["proxy_risk_assessments"]
        fk = [fk for fk in table.foreign_keys if fk.parent.name == "entry_verification_id"][0]
        assert fk.ondelete is None or fk.ondelete != "CASCADE"

    def test_no_unique_constraint_on_entry_verification_id_for_assessments(self):
        """ProxyRiskAssessment allows multiple assessments per entry (historical)."""
        table = Base.metadata.tables["proxy_risk_assessments"]
        from sqlalchemy import UniqueConstraint
        for constraint in table.constraints:
            if isinstance(constraint, UniqueConstraint):
                col_names = {col.name for col in constraint.columns}
                assert "entry_verification_id" not in col_names
