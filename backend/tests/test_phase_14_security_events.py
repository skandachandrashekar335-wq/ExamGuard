"""Phase 14 — Security Event Management Tests.

Tests for security event and alert models, services, and API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.models.security_event import (
    SecurityAlert,
    SecurityAlertStatus,
    SecurityEvent,
    SecurityEventSeverity,
    SecurityEventType,
)
from app.core.database import get_db
from app.main import app
from app.services import security_alert as alert_svc
from app.services import security_event as event_svc


@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session(db_engine):
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def client(db_engine):
    SessionLocal = sessionmaker(bind=db_engine)

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _clean_tables(db_engine):
    """Clean security tables before each test."""
    with db_engine.connect() as conn:
        conn.execute(text("DELETE FROM security_alerts"))
        conn.execute(text("DELETE FROM security_events"))
        conn.commit()
    yield
    with db_engine.connect() as conn:
        conn.execute(text("DELETE FROM security_alerts"))
        conn.execute(text("DELETE FROM security_events"))
        conn.commit()


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------


class TestSecurityEventModel:
    def test_create_event(self, db_session):
        event = SecurityEvent(
            event_type=SecurityEventType.SIGNAL_DETECTED.value,
            severity=SecurityEventSeverity.MEDIUM.value,
            entity_type="EntryVerification",
            entity_id=1,
            source="signal_detection",
            description="Test event",
        )
        db_session.add(event)
        db_session.flush()
        assert event.id is not None
        assert event.event_type == "SIGNAL_DETECTED"
        assert event.severity == "MEDIUM"
        assert event.created_at is not None

    def test_event_nullable_fields(self, db_session):
        event = SecurityEvent(
            event_type=SecurityEventType.MANUAL_FLAG.value,
            severity=SecurityEventSeverity.LOW.value,
            entity_type="Student",
            entity_id=1,
            source="manual",
        )
        db_session.add(event)
        db_session.flush()
        assert event.entry_verification_id is None
        assert event.student_id is None
        assert event.exam_id is None
        assert event.description is None
        assert event.metadata_json is None


class TestSecurityAlertModel:
    def test_create_alert(self, db_session):
        event = SecurityEvent(
            event_type=SecurityEventType.RISK_THRESHOLD_EXCEEDED.value,
            severity=SecurityEventSeverity.HIGH.value,
            entity_type="EntryVerification",
            entity_id=1,
            source="proxy_risk",
        )
        db_session.add(event)
        db_session.flush()

        alert = SecurityAlert(
            security_event_id=event.id,
            severity=SecurityEventSeverity.HIGH.value,
            message="High risk detected",
        )
        db_session.add(alert)
        db_session.flush()
        assert alert.id is not None
        assert alert.status == SecurityAlertStatus.OPEN.value
        assert alert.created_at is not None
        assert alert.updated_at is not None

    def test_alert_lifecycle_fields(self, db_session):
        event = SecurityEvent(
            event_type=SecurityEventType.ENTRY_ESCALATED.value,
            severity=SecurityEventSeverity.CRITICAL.value,
            entity_type="EntryVerification",
            entity_id=1,
            source="monitoring",
        )
        db_session.add(event)
        db_session.flush()

        alert = SecurityAlert(
            security_event_id=event.id,
            severity=SecurityEventSeverity.CRITICAL.value,
            message="Critical alert",
        )
        db_session.add(alert)
        db_session.flush()
        assert alert.assigned_to is None
        assert alert.acknowledged_at is None
        assert alert.resolved_at is None
        assert alert.resolution_notes is None


# ---------------------------------------------------------------------------
# Service Tests — Security Events
# ---------------------------------------------------------------------------


class TestSecurityEventService:
    def test_create_event_service(self, db_session):
        event = event_svc.create_security_event(
            db_session,
            event_type=SecurityEventType.SIGNAL_DETECTED,
            severity=SecurityEventSeverity.MEDIUM,
            entity_type="EntryVerification",
            entity_id=42,
            source="signal_detection",
            description="Test signal",
            metadata={"signal_type": "DUPLICATE_ENTRY"},
            entry_verification_id=10,
            student_id=5,
            exam_id=3,
        )
        assert event.id is not None
        assert event.entity_id == 42
        assert event.source == "signal_detection"
        assert event.metadata_json is not None

    def test_list_events(self, db_session):
        for i in range(5):
            event_svc.create_security_event(
                db_session,
                event_type=SecurityEventType.SIGNAL_DETECTED,
                severity=SecurityEventSeverity.LOW,
                entity_type="EntryVerification",
                entity_id=i,
                source="test",
            )
        result = event_svc.list_security_events(db_session, page=1, page_size=3)
        assert result["total"] == 5
        assert len(result["items"]) == 3
        assert result["page"] == 1
        assert result["page_size"] == 3

    def test_list_events_filter_type(self, db_session):
        event_svc.create_security_event(
            db_session,
            event_type=SecurityEventType.SIGNAL_DETECTED,
            severity=SecurityEventSeverity.LOW,
            entity_type="EntryVerification",
            entity_id=1,
            source="test",
        )
        event_svc.create_security_event(
            db_session,
            event_type=SecurityEventType.MANUAL_FLAG,
            severity=SecurityEventSeverity.LOW,
            entity_type="Student",
            entity_id=1,
            source="test",
        )
        result = event_svc.list_security_events(
            db_session, event_type="SIGNAL_DETECTED"
        )
        assert result["total"] == 1
        assert result["items"][0].event_type == "SIGNAL_DETECTED"

    def test_get_event(self, db_session):
        event = event_svc.create_security_event(
            db_session,
            event_type=SecurityEventType.MANUAL_FLAG,
            severity=SecurityEventSeverity.INFO,
            entity_type="Exam",
            entity_id=1,
            source="manual",
        )
        found = event_svc.get_security_event(db_session, event.id)
        assert found.id == event.id

    def test_get_event_not_found(self, db_session):
        with pytest.raises(LookupError):
            event_svc.get_security_event(db_session, 99999)

    def test_count_events(self, db_session):
        count_before = event_svc.count_security_events(db_session)
        event_svc.create_security_event(
            db_session,
            event_type=SecurityEventType.SIGNAL_DETECTED,
            severity=SecurityEventSeverity.LOW,
            entity_type="Test",
            entity_id=1,
            source="test",
        )
        count_after = event_svc.count_security_events(db_session)
        assert count_after == count_before + 1


# ---------------------------------------------------------------------------
# Service Tests — Security Alerts
# ---------------------------------------------------------------------------


class TestSecurityAlertService:
    def _make_event(self, db_session):
        return event_svc.create_security_event(
            db_session,
            event_type=SecurityEventType.RISK_THRESHOLD_EXCEEDED,
            severity=SecurityEventSeverity.HIGH,
            entity_type="EntryVerification",
            entity_id=1,
            source="proxy_risk",
        )

    def test_create_alert(self, db_session):
        event = self._make_event(db_session)
        alert = alert_svc.create_security_alert(
            db_session,
            security_event_id=event.id,
            severity=SecurityEventSeverity.HIGH,
            message="High risk detected",
        )
        assert alert.id is not None
        assert alert.status == "OPEN"

    def test_create_alert_event_not_found(self, db_session):
        with pytest.raises(LookupError):
            alert_svc.create_security_alert(
                db_session,
                security_event_id=99999,
                severity=SecurityEventSeverity.HIGH,
                message="Test",
            )

    def test_acknowledge_alert(self, db_session):
        event = self._make_event(db_session)
        alert = alert_svc.create_security_alert(
            db_session,
            security_event_id=event.id,
            severity=SecurityEventSeverity.HIGH,
            message="Test alert",
        )
        result = alert_svc.acknowledge_alert(
            db_session, alert.id, assigned_to="operator1"
        )
        assert result.status == "ACKNOWLEDGED"
        assert result.acknowledged_at is not None
        assert result.assigned_to == "operator1"

    def test_acknowledge_wrong_status(self, db_session):
        event = self._make_event(db_session)
        alert = alert_svc.create_security_alert(
            db_session,
            security_event_id=event.id,
            severity=SecurityEventSeverity.HIGH,
            message="Test",
        )
        alert_svc.acknowledge_alert(db_session, alert.id)
        with pytest.raises(ValueError, match="Cannot acknowledge"):
            alert_svc.acknowledge_alert(db_session, alert.id)

    def test_resolve_alert(self, db_session):
        event = self._make_event(db_session)
        alert = alert_svc.create_security_alert(
            db_session,
            security_event_id=event.id,
            severity=SecurityEventSeverity.HIGH,
            message="Test",
        )
        result = alert_svc.resolve_alert(
            db_session,
            alert.id,
            resolution_notes="Resolved by manual review",
            assigned_to="operator1",
        )
        assert result.status == "RESOLVED"
        assert result.resolved_at is not None
        assert result.resolution_notes == "Resolved by manual review"

    def test_resolve_after_acknowledge(self, db_session):
        event = self._make_event(db_session)
        alert = alert_svc.create_security_alert(
            db_session,
            security_event_id=event.id,
            severity=SecurityEventSeverity.HIGH,
            message="Test",
        )
        alert_svc.acknowledge_alert(db_session, alert.id)
        result = alert_svc.resolve_alert(db_session, alert.id)
        assert result.status == "RESOLVED"

    def test_resolve_wrong_status(self, db_session):
        event = self._make_event(db_session)
        alert = alert_svc.create_security_alert(
            db_session,
            security_event_id=event.id,
            severity=SecurityEventSeverity.HIGH,
            message="Test",
        )
        alert_svc.resolve_alert(db_session, alert.id)
        with pytest.raises(ValueError, match="Cannot resolve"):
            alert_svc.resolve_alert(db_session, alert.id)

    def test_dismiss_alert(self, db_session):
        event = self._make_event(db_session)
        alert = alert_svc.create_security_alert(
            db_session,
            security_event_id=event.id,
            severity=SecurityEventSeverity.LOW,
            message="Test",
        )
        result = alert_svc.dismiss_alert(
            db_session,
            alert.id,
            reason="False positive",
        )
        assert result.status == "DISMISSED"
        assert result.resolution_notes == "False positive"

    def test_dismiss_wrong_status(self, db_session):
        event = self._make_event(db_session)
        alert = alert_svc.create_security_alert(
            db_session,
            security_event_id=event.id,
            severity=SecurityEventSeverity.LOW,
            message="Test",
        )
        alert_svc.dismiss_alert(db_session, alert.id, reason="test")
        with pytest.raises(ValueError, match="Cannot dismiss"):
            alert_svc.dismiss_alert(db_session, alert.id, reason="test again")

    def test_list_alerts(self, db_session):
        event = self._make_event(db_session)
        for i in range(3):
            alert_svc.create_security_alert(
                db_session,
                security_event_id=event.id,
                severity=SecurityEventSeverity.HIGH,
                message=f"Alert {i}",
            )
        result = alert_svc.list_security_alerts(db_session, page=1, page_size=2)
        assert result["total"] == 3
        assert len(result["items"]) == 2

    def test_list_alerts_filter_status(self, db_session):
        event = self._make_event(db_session)
        alert_svc.create_security_alert(
            db_session,
            security_event_id=event.id,
            severity=SecurityEventSeverity.HIGH,
            message="Open alert",
        )
        alert2 = alert_svc.create_security_alert(
            db_session,
            security_event_id=event.id,
            severity=SecurityEventSeverity.HIGH,
            message="Resolved alert",
        )
        alert_svc.resolve_alert(db_session, alert2.id)
        result = alert_svc.list_security_alerts(db_session, status="OPEN")
        assert result["total"] == 1
        assert result["items"][0].status == "OPEN"


# ---------------------------------------------------------------------------
# API Tests — Security Events
# ---------------------------------------------------------------------------


class TestSecurityEventsAPI:
    def test_list_events_empty(self, client):
        resp = client.get("/api/v1/security-events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_events_with_data(self, client, db_session):
        event_svc.create_security_event(
            db_session,
            event_type=SecurityEventType.SIGNAL_DETECTED,
            severity=SecurityEventSeverity.MEDIUM,
            entity_type="EntryVerification",
            entity_id=1,
            source="signal_detection",
        )
        db_session.commit()
        resp = client.get("/api/v1/security-events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["event_type"] == "SIGNAL_DETECTED"

    def test_list_events_filter(self, client, db_session):
        event_svc.create_security_event(
            db_session,
            event_type=SecurityEventType.SIGNAL_DETECTED,
            severity=SecurityEventSeverity.LOW,
            entity_type="EntryVerification",
            entity_id=1,
            source="test",
        )
        event_svc.create_security_event(
            db_session,
            event_type=SecurityEventType.MANUAL_FLAG,
            severity=SecurityEventSeverity.LOW,
            entity_type="Student",
            entity_id=1,
            source="test",
        )
        db_session.commit()
        resp = client.get(
            "/api/v1/security-events",
            params={"event_type": "SIGNAL_DETECTED"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_get_event(self, client, db_session):
        event = event_svc.create_security_event(
            db_session,
            event_type=SecurityEventType.MANUAL_FLAG,
            severity=SecurityEventSeverity.INFO,
            entity_type="Exam",
            entity_id=1,
            source="manual",
        )
        db_session.commit()
        resp = client.get(f"/api/v1/security-events/{event.id}")
        assert resp.status_code == 200
        assert resp.json()["event_type"] == "MANUAL_FLAG"

    def test_get_event_404(self, client):
        resp = client.get("/api/v1/security-events/99999")
        assert resp.status_code == 404

    def test_pagination(self, client, db_session):
        for i in range(5):
            event_svc.create_security_event(
                db_session,
                event_type=SecurityEventType.SIGNAL_DETECTED,
                severity=SecurityEventSeverity.LOW,
                entity_type="Test",
                entity_id=i,
                source="test",
            )
        db_session.commit()
        resp = client.get(
            "/api/v1/security-events",
            params={"page": 1, "page_size": 2},
        )
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2


# ---------------------------------------------------------------------------
# API Tests — Security Alerts
# ---------------------------------------------------------------------------


class TestSecurityAlertsAPI:
    def _create_event(self, db_session):
        event = event_svc.create_security_event(
            db_session,
            event_type=SecurityEventType.RISK_THRESHOLD_EXCEEDED,
            severity=SecurityEventSeverity.HIGH,
            entity_type="EntryVerification",
            entity_id=1,
            source="proxy_risk",
        )
        db_session.commit()
        return event

    def test_list_alerts_empty(self, client):
        resp = client.get("/api/v1/security-alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_create_and_list_alerts(self, client, db_session):
        event = self._create_event(db_session)
        alert = alert_svc.create_security_alert(
            db_session,
            security_event_id=event.id,
            severity=SecurityEventSeverity.HIGH,
            message="High risk",
        )
        db_session.commit()
        resp = client.get("/api/v1/security-alerts")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_get_alert(self, client, db_session):
        event = self._create_event(db_session)
        alert = alert_svc.create_security_alert(
            db_session,
            security_event_id=event.id,
            severity=SecurityEventSeverity.HIGH,
            message="Test",
        )
        db_session.commit()
        resp = client.get(f"/api/v1/security-alerts/{alert.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "OPEN"

    def test_get_alert_404(self, client):
        resp = client.get("/api/v1/security-alerts/99999")
        assert resp.status_code == 404

    def test_acknowledge_alert(self, client, db_session):
        event = self._create_event(db_session)
        alert = alert_svc.create_security_alert(
            db_session,
            security_event_id=event.id,
            severity=SecurityEventSeverity.HIGH,
            message="Test",
        )
        db_session.commit()
        resp = client.post(
            f"/api/v1/security-alerts/{alert.id}/acknowledge",
            json={"assigned_to": "operator1"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ACKNOWLEDGED"

    def test_resolve_alert(self, client, db_session):
        event = self._create_event(db_session)
        alert = alert_svc.create_security_alert(
            db_session,
            security_event_id=event.id,
            severity=SecurityEventSeverity.HIGH,
            message="Test",
        )
        db_session.commit()
        resp = client.post(
            f"/api/v1/security-alerts/{alert.id}/resolve",
            json={"resolution_notes": "Reviewed and resolved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "RESOLVED"

    def test_dismiss_alert(self, client, db_session):
        event = self._create_event(db_session)
        alert = alert_svc.create_security_alert(
            db_session,
            security_event_id=event.id,
            severity=SecurityEventSeverity.LOW,
            message="Test",
        )
        db_session.commit()
        resp = client.post(
            f"/api/v1/security-alerts/{alert.id}/dismiss",
            json={"reason": "False positive"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "DISMISSED"

    def test_acknowledge_already_acknowledged(self, client, db_session):
        event = self._create_event(db_session)
        alert = alert_svc.create_security_alert(
            db_session,
            security_event_id=event.id,
            severity=SecurityEventSeverity.HIGH,
            message="Test",
        )
        db_session.commit()
        client.post(f"/api/v1/security-alerts/{alert.id}/acknowledge", json={})
        resp = client.post(
            f"/api/v1/security-alerts/{alert.id}/acknowledge", json={}
        )
        assert resp.status_code == 422

    def test_filter_by_status(self, client, db_session):
        event = self._create_event(db_session)
        alert_svc.create_security_alert(
            db_session,
            security_event_id=event.id,
            severity=SecurityEventSeverity.HIGH,
            message="Open",
        )
        alert2 = alert_svc.create_security_alert(
            db_session,
            security_event_id=event.id,
            severity=SecurityEventSeverity.HIGH,
            message="Resolved",
        )
        alert_svc.resolve_alert(db_session, alert2.id)
        db_session.commit()
        resp = client.get(
            "/api/v1/security-alerts",
            params={"status": "OPEN"},
        )
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["status"] == "OPEN"
