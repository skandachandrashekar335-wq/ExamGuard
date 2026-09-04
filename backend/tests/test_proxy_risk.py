"""Tests for proxy risk scoring and assessment service.

Covers:
- Pure scoring: empty signals, single signals, multiple signals, weight lookup
- Score capping, risk level classification, unknown signal types
- Explanation determinism and content
- signals_summary_json correctness
- DB assessment: creation, persistence, historical (multiple per entry verification)
- Edge cases: entry verification not found, no signals, all zero weights
- Privacy: no biometric data in explanation or summary
- Policy version tracking
"""

import json
from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models import Base
from app.models.entry_point import EntryPoint
from app.models.entry_verification import (
    EntryVerification,
    EntryVerificationStatus,
)
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration
from app.models.proxy_risk import (
    ProxyRiskAssessment,
    RiskLevel,
    SecuritySignal,
)
from app.models.student import Student
from app.models.subject import Subject
from app.services.proxy_risk import (
    RiskAssessmentResult,
    _build_explanation,
    _build_signals_summary,
    _classify_risk_level,
    _parse_weights,
    assess_entry_verification,
    compute_risk_score,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DB_URL, echo=False)
TestSession = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables for each test and drop after."""
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def settings():
    return get_settings()


def _make_entry_verification(db) -> EntryVerification:
    """Create a minimal EntryVerification with required FK dependencies."""
    subject = Subject(name="Mathematics", code="MATH101", department="CS", semester=6)
    db.add(subject)
    db.commit()
    db.refresh(subject)

    student = Student(name="Test Student", usn="1MS21CS001")
    db.add(student)
    db.commit()
    db.refresh(student)

    exam = Exam(
        subject_id=subject.id,
        exam_name="Test Exam",
        exam_date=date(2026, 9, 15),
        start_time=time(9, 0),
        end_time=time(12, 0),
        semester=6,
        department="CS",
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    hall = ExamHall(building="TestBuilding", room_number="101", capacity=50)
    db.add(hall)
    db.commit()
    db.refresh(hall)

    entry_point = EntryPoint(
        name="Main Gate", code="MAIN_GATE", exam_hall_id=hall.id
    )
    db.add(entry_point)
    db.commit()
    db.refresh(entry_point)

    registration = ExamRegistration(student_id=student.id, exam_id=exam.id)
    db.add(registration)
    db.commit()
    db.refresh(registration)

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


def _make_signal(
    entry_verification_id: int,
    signal_type: str,
    strength: str = "MODERATE",
    source: str = "test",
    description: str | None = None,
    evidence_json: str | None = None,
) -> SecuritySignal:
    """Create a SecuritySignal without persisting."""
    return SecuritySignal(
        entry_verification_id=entry_verification_id,
        signal_type=signal_type,
        strength=strength,
        source=source,
        description=description,
        evidence_json=evidence_json,
    )


# ---------------------------------------------------------------------------
# Unit tests: _parse_weights
# ---------------------------------------------------------------------------


class TestParseWeights:
    def test_empty_string(self):
        assert _parse_weights("") == {}

    def test_none_like_empty(self):
        assert _parse_weights("   ") == {}

    def test_single_weight(self):
        result = _parse_weights("DUPLICATE_ENTRY:30")
        assert result == {"DUPLICATE_ENTRY": 30.0}

    def test_multiple_weights(self):
        result = _parse_weights("A:10,B:20,C:30")
        assert result == {"A": 10.0, "B": 20.0, "C": 30.0}

    def test_float_weights(self):
        result = _parse_weights("X:0.5,Y:1.5")
        assert result == {"X": 0.5, "Y": 1.5}

    def test_whitespace_handling(self):
        result = _parse_weights(" A : 10 , B : 20 ")
        assert result == {"A": 10.0, "B": 20.0}

    def test_invalid_value_skipped(self):
        result = _parse_weights("A:10,B:notanumber,C:30")
        assert "A" in result
        assert "B" not in result
        assert "C" in result

    def test_empty_key_skipped(self):
        result = _parse_weights(":10,B:20")
        assert "" not in result
        assert result == {"B": 20.0}


# ---------------------------------------------------------------------------
# Unit tests: _classify_risk_level
# ---------------------------------------------------------------------------


class TestClassifyRiskLevel:
    def test_low(self, settings):
        assert _classify_risk_level(0.0, settings) == RiskLevel.LOW.value
        assert _classify_risk_level(29.9, settings) == RiskLevel.LOW.value

    def test_elevated(self, settings):
        assert (
            _classify_risk_level(30.0, settings) == RiskLevel.ELEVATED.value
        )
        assert (
            _classify_risk_level(59.9, settings) == RiskLevel.ELEVATED.value
        )

    def test_high(self, settings):
        assert _classify_risk_level(60.0, settings) == RiskLevel.HIGH.value
        assert _classify_risk_level(79.9, settings) == RiskLevel.HIGH.value

    def test_critical(self, settings):
        assert (
            _classify_risk_level(80.0, settings) == RiskLevel.CRITICAL.value
        )
        assert (
            _classify_risk_level(150.0, settings) == RiskLevel.CRITICAL.value
        )

    def test_exact_boundary_elevated(self, settings):
        assert (
            _classify_risk_level(
                settings.PROXY_RISK_ELEVATED_THRESHOLD, settings
            )
            == RiskLevel.ELEVATED.value
        )

    def test_exact_boundary_high(self, settings):
        assert (
            _classify_risk_level(
                settings.PROXY_RISK_HIGH_THRESHOLD, settings
            )
            == RiskLevel.HIGH.value
        )

    def test_exact_boundary_critical(self, settings):
        assert (
            _classify_risk_level(
                settings.PROXY_RISK_CRITICAL_THRESHOLD, settings
            )
            == RiskLevel.CRITICAL.value
        )


# ---------------------------------------------------------------------------
# Unit tests: compute_risk_score (pure)
# ---------------------------------------------------------------------------


class TestComputeRiskScore:
    def test_empty_signals(self):
        result = compute_risk_score([])
        assert result.risk_score == 0.0
        assert result.risk_level == RiskLevel.LOW.value
        assert result.signal_count == 0
        assert result.strong_signal_count == 0
        assert "No security signals" in result.explanation

    def test_single_known_signal(self, settings):
        sig = _make_signal(1, "DUPLICATE_ENTRY", strength="MODERATE")
        result = compute_risk_score([sig])

        # DUPLICATE_ENTRY weight is 30 per default config
        assert result.signal_count == 1
        assert result.strong_signal_count == 0
        assert result.risk_score == 30.0
        assert result.risk_level == RiskLevel.ELEVATED.value
        assert len(result.signals_detail) == 1
        assert result.signals_detail[0]["type"] == "DUPLICATE_ENTRY"
        assert result.signals_detail[0]["strength"] == "MODERATE"
        assert result.signals_detail[0]["weight"] == 30.0

    def test_single_unknown_type_has_zero_weight(self):
        sig = _make_signal(1, "UNKNOWN_TYPE_XYZ", strength="STRONG")
        result = compute_risk_score([sig])

        assert result.signal_count == 1
        assert result.strong_signal_count == 1
        assert result.risk_score == 0.0
        assert result.risk_level == RiskLevel.LOW.value
        assert result.signals_detail[0]["weight"] == 0.0

    def test_multiple_signals_sum(self):
        signals = [
            _make_signal(1, "DUPLICATE_ENTRY", strength="MODERATE"),   # 30
            _make_signal(1, "UNUSUAL_ENTRY_POINT", strength="WEAK"),  # 15
            _make_signal(1, "UNUSUAL_TIME", strength="WEAK"),         # 10
        ]
        result = compute_risk_score(signals)

        assert result.signal_count == 3
        assert result.risk_score == 55.0  # 30 + 15 + 10
        assert result.risk_level == RiskLevel.ELEVATED.value  # 55 < 60 HIGH threshold

    def test_score_capped_at_max(self):
        # 5 × DUPLICATE_ENTRY (30) = 150, capped at 100
        signals = [
            _make_signal(1, "DUPLICATE_ENTRY", strength="MODERATE")
            for _ in range(5)
        ]
        result = compute_risk_score(signals)

        assert result.risk_score == 100.0
        assert result.risk_level == RiskLevel.CRITICAL.value

    def test_strong_signal_count(self):
        signals = [
            _make_signal(1, "SEAT_MISMATCH", strength="STRONG"),
            _make_signal(1, "IDENTITY_MISMATCH", strength="STRONG"),
            _make_signal(1, "DUPLICATE_ENTRY", strength="MODERATE"),
            _make_signal(1, "UNUSUAL_TIME", strength="WEAK"),
        ]
        result = compute_risk_score(signals)

        assert result.strong_signal_count == 2
        assert result.signal_count == 4

    def test_all_strengths_counted(self):
        signals = [
            _make_signal(1, "X", strength="STRONG"),
            _make_signal(1, "Y", strength="MODERATE"),
            _make_signal(1, "Z", strength="WEAK"),
            _make_signal(1, "W", strength="INFORMATIONAL"),
        ]
        result = compute_risk_score(signals)

        strength_counts = {}
        for s in result.signals_detail:
            strength_counts[s["strength"]] = (
                strength_counts.get(s["strength"], 0) + 1
            )
        assert strength_counts == {
            "STRONG": 1,
            "MODERATE": 1,
            "WEAK": 1,
            "INFORMATIONAL": 1,
        }

    def test_known_strong_signal(self):
        sig = _make_signal(1, "IDENTITY_MISMATCH", strength="STRONG")
        result = compute_risk_score([sig])

        # IDENTITY_MISMATCH weight is 45
        assert result.risk_score == 45.0
        assert result.strong_signal_count == 1
        assert result.risk_level == RiskLevel.ELEVATED.value

    def test_mixed_known_and_unknown(self):
        signals = [
            _make_signal(1, "DUPLICATE_ENTRY", strength="MODERATE"),  # 30
            _make_signal(1, "SOME_NEW_TYPE", strength="STRONG"),      # 0
        ]
        result = compute_risk_score(signals)

        assert result.risk_score == 30.0
        assert result.strong_signal_count == 1  # SOME_NEW_TYPE is STRONG

    def test_explanation_contains_signal_types(self):
        signals = [
            _make_signal(1, "DUPLICATE_ENTRY", strength="MODERATE"),
            _make_signal(1, "SEAT_MISMATCH", strength="STRONG"),
        ]
        result = compute_risk_score(signals)

        assert "DUPLICATE_ENTRY" in result.explanation
        assert "SEAT_MISMATCH" in result.explanation
        assert "2 signals" in result.explanation

    def test_explanation_no_biometric_data(self):
        sig = _make_signal(1, "IDENTITY_MISMATCH", strength="STRONG")
        result = compute_risk_score([sig])

        # Should never contain biometric terms
        lower_explanation = result.explanation.lower()
        assert "face" not in lower_explanation
        assert "similarity" not in lower_explanation
        assert "embedding" not in lower_explanation
        assert "biometric" not in lower_explanation

    def test_explanation_deterministic(self):
        signals = [
            _make_signal(1, "A", strength="STRONG"),
            _make_signal(1, "B", strength="MODERATE"),
        ]
        r1 = compute_risk_score(signals)
        r2 = compute_risk_score(signals)
        assert r1.explanation == r2.explanation

    def test_explanation_mentions_capping_when_applicable(self):
        # Exceed max
        signals = [
            _make_signal(1, "IDENTITY_MISMATCH", strength="STRONG"),  # 45
            _make_signal(1, "SEAT_MISMATCH", strength="STRONG"),  # 40
            _make_signal(1, "DOCUMENT_ANOMALY", strength="STRONG"),  # 35
            # total = 120, capped to 100
        ]
        result = compute_risk_score(signals)

        assert "capped" in result.explanation.lower()
        assert "120" in result.explanation
        assert "100" in result.explanation


# ---------------------------------------------------------------------------
# Unit tests: _build_explanation
# ---------------------------------------------------------------------------


class TestBuildExplanation:
    def test_empty(self):
        explanation = _build_explanation(
            signal_count=0,
            strong_count=0,
            total_score=0.0,
            capped_score=0.0,
            risk_level="LOW",
            signals_detail=[],
        )
        assert "0 signals" in explanation
        assert "LOW" in explanation

    def test_strong_and_moderate(self):
        explanation = _build_explanation(
            signal_count=3,
            strong_count=1,
            total_score=55.0,
            capped_score=55.0,
            risk_level="HIGH",
            signals_detail=[
                {"type": "A", "strength": "STRONG", "weight": 40},
                {"type": "B", "strength": "MODERATE", "weight": 15},
            ],
        )
        assert "1 strong" in explanation
        assert "1 moderate" in explanation
        assert "HIGH" in explanation

    def test_no_capping_message_when_equal(self):
        explanation = _build_explanation(
            signal_count=1,
            strong_count=0,
            total_score=30.0,
            capped_score=30.0,
            risk_level="ELEVATED",
            signals_detail=[],
        )
        assert "capped" not in explanation.lower()
        assert "30.0" in explanation


# ---------------------------------------------------------------------------
# Unit tests: _build_signals_summary
# ---------------------------------------------------------------------------


class TestBuildSignalsSummary:
    def test_json_structure(self):
        result = RiskAssessmentResult(
            risk_score=45.0,
            risk_level="ELEVATED",
            signal_count=2,
            strong_signal_count=1,
            explanation="test explanation",
            signals_detail=[
                {"type": "A", "strength": "STRONG", "weight": 40},
                {"type": "B", "strength": "WEAK", "weight": 5},
            ],
        )
        raw = _build_signals_summary(result)
        parsed = json.loads(raw)

        assert parsed["signal_count"] == 2
        assert parsed["strong_signal_count"] == 1
        assert parsed["explanation"] == "test explanation"
        assert len(parsed["signals"]) == 2
        assert parsed["signals"][0]["type"] == "A"

    def test_valid_json(self):
        result = RiskAssessmentResult(
            risk_score=0.0,
            risk_level="LOW",
            signal_count=0,
            strong_signal_count=0,
            explanation="empty",
        )
        raw = _build_signals_summary(result)
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# Integration tests: assess_entry_verification (DB)
# ---------------------------------------------------------------------------


class TestAssessEntryVerification:
    def test_creates_assessment_no_signals(self, db):
        ev = _make_entry_verification(db)

        assessment = assess_entry_verification(db, ev.id)

        assert isinstance(assessment, ProxyRiskAssessment)
        assert assessment.entry_verification_id == ev.id
        assert assessment.risk_score == 0.0
        assert assessment.risk_level == RiskLevel.LOW.value
        assert assessment.policy_version == get_settings().PROXY_RISK_POLICY_VERSION
        assert assessment.assessed_at is not None

        # Verify persistence
        saved = (
            db.query(ProxyRiskAssessment)
            .filter(ProxyRiskAssessment.id == assessment.id)
            .first()
        )
        assert saved is not None

    def test_creates_assessment_with_signals(self, db):
        ev = _make_entry_verification(db)
        sig1 = _make_signal(ev.id, "DUPLICATE_ENTRY", strength="MODERATE")
        sig2 = _make_signal(ev.id, "SEAT_MISMATCH", strength="STRONG")
        db.add_all([sig1, sig2])
        db.commit()

        assessment = assess_entry_verification(db, ev.id)

        assert assessment.risk_score == 70.0  # 30 + 40
        assert assessment.risk_level == RiskLevel.HIGH.value

        summary = json.loads(assessment.signals_summary_json)
        assert summary["signal_count"] == 2
        assert summary["strong_signal_count"] == 1

    def test_historical_multiple_assessments(self, db):
        ev = _make_entry_verification(db)

        a1 = assess_entry_verification(db, ev.id)
        a2 = assess_entry_verification(db, ev.id)

        assert a1.id != a2.id
        assert a1.entry_verification_id == a2.entry_verification_id
        assert a1.risk_score == a2.risk_score  # same signals = same score

        count = (
            db.query(ProxyRiskAssessment)
            .filter(ProxyRiskAssessment.entry_verification_id == ev.id)
            .count()
        )
        assert count == 2

    def test_entry_verification_not_found(self, db):
        with pytest.raises(ValueError, match="not found"):
            assess_entry_verification(db, 99999)

    def test_policy_version_recorded(self, db):
        ev = _make_entry_verification(db)
        settings = get_settings()

        assessment = assess_entry_verification(db, ev.id)

        assert assessment.policy_version == settings.PROXY_RISK_POLICY_VERSION

    def test_summary_json_valid(self, db):
        ev = _make_entry_verification(db)
        sig = _make_signal(ev.id, "DOCUMENT_ANOMALY", strength="STRONG")
        db.add(sig)
        db.commit()

        assessment = assess_entry_verification(db, ev.id)

        summary = json.loads(assessment.signals_summary_json)
        assert "signal_count" in summary
        assert "strong_signal_count" in summary
        assert "explanation" in summary
        assert "signals" in summary

    def test_assessment_does_not_modify_entry_verification(self, db):
        ev = _make_entry_verification(db)
        original_status = ev.status
        original_id = ev.id

        assess_entry_verification(db, ev.id)

        db.refresh(ev)
        assert ev.status == original_status
        assert ev.id == original_id

    def test_assessment_with_mixed_known_unknown_signals(self, db):
        ev = _make_entry_verification(db)
        sig1 = _make_signal(ev.id, "DUPLICATE_ENTRY", strength="MODERATE")  # 30
        sig2 = _make_signal(ev.id, "CUSTOM_NEW_SIGNAL", strength="STRONG")  # 0
        db.add_all([sig1, sig2])
        db.commit()

        assessment = assess_entry_verification(db, ev.id)

        assert assessment.risk_score == 30.0
        summary = json.loads(assessment.signals_summary_json)
        assert summary["signal_count"] == 2
        assert summary["strong_signal_count"] == 1

    def test_assessment_explanation_no_biometric_data(self, db):
        ev = _make_entry_verification(db)
        sig = _make_signal(ev.id, "IDENTITY_MISMATCH", strength="STRONG")
        db.add(sig)
        db.commit()

        assessment = assess_entry_verification(db, ev.id)
        summary = json.loads(assessment.signals_summary_json)
        explanation = summary["explanation"].lower()

        assert "face" not in explanation
        assert "similarity" not in explanation
        assert "embedding" not in explanation
        assert "biometric" not in explanation

    def test_assessment_score_capped(self, db):
        ev = _make_entry_verification(db)
        # 5 × DUPLICATE_ENTRY = 150, capped at 100
        for _ in range(5):
            sig = _make_signal(ev.id, "DUPLICATE_ENTRY", strength="MODERATE")
            db.add(sig)
        db.commit()

        assessment = assess_entry_verification(db, ev.id)

        assert assessment.risk_score == 100.0
        assert assessment.risk_level == RiskLevel.CRITICAL.value
