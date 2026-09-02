import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.import_audit_log import (
    ImportAuditLog,
    ImportAuditStatus,
    ImportOperation,
    ImportType,
)
from app.models.student import Student


@pytest.fixture(autouse=True)
def cleanup():
    db = SessionLocal()
    try:
        db.execute(delete(ImportAuditLog))
        db.execute(delete(Student).where(Student.usn.ilike("AUDIMP%")))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


class TestImportAuditLogModel:
    def test_creation(self):
        log = ImportAuditLog(
            import_type=ImportType.STUDENTS.value,
            operation=ImportOperation.IMPORT.value,
            status=ImportAuditStatus.STARTED.value,
            total_rows=10,
            successful_rows=0,
            skipped_rows=0,
            failed_rows=0,
        )
        assert log.import_type == "students"
        assert log.operation == "import"
        assert log.status == "started"
        assert log.total_rows == 10
        assert log.successful_rows == 0
        assert log.skipped_rows == 0
        assert log.failed_rows == 0
        assert log.error_summary is None
        assert log.actor is None
        assert log.completed_at is None

    def test_import_type_enum_values(self):
        assert ImportType.STUDENTS.value == "students"
        assert ImportType.SUBJECTS_EXAMS.value == "subjects_exams"
        assert ImportType.REGISTRATIONS.value == "registrations"
        assert ImportType.REGISTRATION_CANCELLATIONS.value == "registration_cancellations"
        assert ImportType.SEAT_ASSIGNMENTS.value == "seat_assignments"
        assert ImportType.SEAT_ASSIGNMENT_CANCELLATIONS.value == "seat_assignment_cancellations"

    def test_operation_enum_values(self):
        assert ImportOperation.IMPORT.value == "import"
        assert ImportOperation.CANCELLATION.value == "cancellation"

    def test_status_enum_values(self):
        assert ImportAuditStatus.STARTED.value == "started"
        assert ImportAuditStatus.COMPLETED.value == "completed"
        assert ImportAuditStatus.COMPLETED_WITH_ERRORS.value == "completed_with_errors"
        assert ImportAuditStatus.FAILED.value == "failed"

    def test_actor_nullable(self):
        log = ImportAuditLog(
            import_type="students",
            operation="import",
            status="started",
            total_rows=0,
        )
        assert log.actor is None

    def test_repr(self):
        log = ImportAuditLog(
            import_type="students",
            operation="import",
            status="started",
            total_rows=0,
        )
        assert "ImportAuditLog" in repr(log)
        assert "students" in repr(log)


class TestAuditLogService:
    def test_create_audit_log(self):
        from app.schemas.import_audit_log import ImportAuditLogCreate
        from app.services.import_audit_log import create_audit_log

        db = SessionLocal()
        try:
            log = create_audit_log(
                db,
                ImportAuditLogCreate(
                    import_type="students",
                    operation="import",
                    total_rows=5,
                ),
            )
            assert log.id is not None
            assert log.import_type == "students"
            assert log.operation == "import"
            assert log.status == "started"
            assert log.total_rows == 5
            assert log.started_at is not None
        finally:
            db.close()

    def test_complete_audit_log_success(self):
        from app.schemas.import_audit_log import ImportAuditLogCreate
        from app.services.import_audit_log import complete_audit_log, create_audit_log

        db = SessionLocal()
        try:
            log = create_audit_log(
                db,
                ImportAuditLogCreate(
                    import_type="students",
                    operation="import",
                    total_rows=3,
                ),
            )
            result = complete_audit_log(
                db, log.id, successful=3, skipped=0, failed=0
            )
            assert result.status == "completed"
            assert result.successful_rows == 3
            assert result.skipped_rows == 0
            assert result.failed_rows == 0
            assert result.completed_at is not None
            assert result.error_summary is None
        finally:
            db.close()

    def test_complete_audit_log_with_errors(self):
        from app.schemas.import_audit_log import ImportAuditLogCreate
        from app.services.import_audit_log import complete_audit_log, create_audit_log

        db = SessionLocal()
        try:
            log = create_audit_log(
                db,
                ImportAuditLogCreate(
                    import_type="students",
                    operation="import",
                    total_rows=5,
                ),
            )
            result = complete_audit_log(
                db, log.id, successful=2, skipped=1, failed=2
            )
            assert result.status == "completed_with_errors"
            assert result.successful_rows == 2
            assert result.skipped_rows == 1
            assert result.failed_rows == 2
        finally:
            db.close()

    def test_complete_audit_log_all_failed(self):
        from app.schemas.import_audit_log import ImportAuditLogCreate
        from app.services.import_audit_log import complete_audit_log, create_audit_log

        db = SessionLocal()
        try:
            log = create_audit_log(
                db,
                ImportAuditLogCreate(
                    import_type="students",
                    operation="import",
                    total_rows=3,
                ),
            )
            result = complete_audit_log(
                db, log.id, successful=0, skipped=0, failed=3
            )
            assert result.status == "failed"
        finally:
            db.close()

    def test_fail_audit_log(self):
        from app.schemas.import_audit_log import ImportAuditLogCreate
        from app.services.import_audit_log import create_audit_log, fail_audit_log

        db = SessionLocal()
        try:
            log = create_audit_log(
                db,
                ImportAuditLogCreate(
                    import_type="students",
                    operation="import",
                    total_rows=0,
                ),
            )
            result = fail_audit_log(
                db, log.id, error_summary="DB connection lost"
            )
            assert result.status == "failed"
            assert result.error_summary == "DB connection lost"
            assert result.completed_at is not None
        finally:
            db.close()

    def test_error_summary_bounded(self):
        from app.schemas.import_audit_log import ImportAuditLogCreate
        from app.services.import_audit_log import (
            MAX_ERROR_SUMMARY_LENGTH,
            complete_audit_log,
            create_audit_log,
        )

        db = SessionLocal()
        try:
            log = create_audit_log(
                db,
                ImportAuditLogCreate(
                    import_type="students",
                    operation="import",
                    total_rows=1,
                ),
            )
            long_error = "x" * 5000
            result = complete_audit_log(
                db, log.id, successful=0, skipped=0, failed=1,
                error_summary=long_error,
            )
            assert len(result.error_summary) == MAX_ERROR_SUMMARY_LENGTH
        finally:
            db.close()

    def test_list_audit_logs(self):
        from app.schemas.import_audit_log import ImportAuditLogCreate
        from app.services.import_audit_log import create_audit_log, list_audit_logs

        db = SessionLocal()
        try:
            create_audit_log(
                db,
                ImportAuditLogCreate(
                    import_type="students", operation="import", total_rows=5
                ),
            )
            create_audit_log(
                db,
                ImportAuditLogCreate(
                    import_type="exams", operation="import", total_rows=3
                ),
            )
            result = list_audit_logs(db)
            assert result["total"] == 2
            assert len(result["items"]) == 2
        finally:
            db.close()

    def test_list_audit_logs_filter_import_type(self):
        from app.schemas.import_audit_log import ImportAuditLogCreate
        from app.services.import_audit_log import create_audit_log, list_audit_logs

        db = SessionLocal()
        try:
            create_audit_log(
                db,
                ImportAuditLogCreate(
                    import_type="students", operation="import", total_rows=5
                ),
            )
            create_audit_log(
                db,
                ImportAuditLogCreate(
                    import_type="exams", operation="import", total_rows=3
                ),
            )
            result = list_audit_logs(db, import_type="students")
            assert result["total"] == 1
            assert result["items"][0].import_type == "students"
        finally:
            db.close()

    def test_list_audit_logs_filter_status(self):
        from app.schemas.import_audit_log import ImportAuditLogCreate
        from app.services.import_audit_log import (
            complete_audit_log,
            create_audit_log,
            list_audit_logs,
        )

        db = SessionLocal()
        try:
            log1 = create_audit_log(
                db,
                ImportAuditLogCreate(
                    import_type="students", operation="import", total_rows=1
                ),
            )
            complete_audit_log(db, log1.id, successful=1, skipped=0, failed=0)
            create_audit_log(
                db,
                ImportAuditLogCreate(
                    import_type="exams", operation="import", total_rows=1
                ),
            )
            result = list_audit_logs(db, status="completed")
            assert result["total"] == 1
            assert result["items"][0].status == "completed"
        finally:
            db.close()

    def test_list_audit_logs_pagination(self):
        from app.schemas.import_audit_log import ImportAuditLogCreate
        from app.services.import_audit_log import create_audit_log, list_audit_logs

        db = SessionLocal()
        try:
            for i in range(5):
                create_audit_log(
                    db,
                    ImportAuditLogCreate(
                        import_type="students", operation="import", total_rows=i
                    ),
                )
            result = list_audit_logs(db, page=1, page_size=2)
            assert result["total"] == 5
            assert len(result["items"]) == 2
            assert result["page"] == 1
            assert result["page_size"] == 2
        finally:
            db.close()

    def test_list_audit_logs_newest_first(self):
        from app.schemas.import_audit_log import ImportAuditLogCreate
        from app.services.import_audit_log import create_audit_log, list_audit_logs

        db = SessionLocal()
        try:
            log_old = create_audit_log(
                db,
                ImportAuditLogCreate(
                    import_type="students", operation="import", total_rows=1
                ),
            )
            log_new = create_audit_log(
                db,
                ImportAuditLogCreate(
                    import_type="exams", operation="import", total_rows=1
                ),
            )
            result = list_audit_logs(db)
            assert result["items"][0].id == log_new.id
            assert result["items"][1].id == log_old.id
        finally:
            db.close()

    def test_get_audit_log(self):
        from app.schemas.import_audit_log import ImportAuditLogCreate
        from app.services.import_audit_log import create_audit_log, get_audit_log

        db = SessionLocal()
        try:
            log = create_audit_log(
                db,
                ImportAuditLogCreate(
                    import_type="students", operation="import", total_rows=5
                ),
            )
            found = get_audit_log(db, log.id)
            assert found is not None
            assert found.id == log.id
        finally:
            db.close()

    def test_get_audit_log_not_found(self):
        from app.services.import_audit_log import get_audit_log

        db = SessionLocal()
        try:
            found = get_audit_log(db, 99999)
            assert found is None
        finally:
            db.close()


class TestAuditLogSchemas:
    def test_import_audit_log_create(self):
        from app.schemas.import_audit_log import ImportAuditLogCreate

        schema = ImportAuditLogCreate(
            import_type="students",
            operation="import",
            total_rows=10,
        )
        assert schema.import_type == "students"
        assert schema.operation == "import"
        assert schema.total_rows == 10

    def test_import_audit_log_summary(self):
        from datetime import datetime, timezone

        from app.schemas.import_audit_log import ImportAuditLogSummary

        now = datetime.now(timezone.utc)
        summary = ImportAuditLogSummary(
            id=1,
            import_type="students",
            operation="import",
            status="completed",
            total_rows=10,
            successful_rows=8,
            skipped_rows=1,
            failed_rows=1,
            started_at=now,
        )
        assert summary.id == 1
        assert summary.completed_at is None

    def test_import_audit_log_detail(self):
        from datetime import datetime, timezone

        from app.schemas.import_audit_log import ImportAuditLogDetail

        now = datetime.now(timezone.utc)
        detail = ImportAuditLogDetail(
            id=1,
            import_type="students",
            operation="import",
            status="completed",
            total_rows=10,
            successful_rows=8,
            skipped_rows=1,
            failed_rows=1,
            error_summary="Some errors occurred",
            actor=None,
            started_at=now,
            completed_at=now,
        )
        assert detail.error_summary == "Some errors occurred"
        assert detail.actor is None


class TestAuditLogApiList:
    def test_list_empty(self, client):
        response = client.get("/api/v1/import/audit")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_returns_logs(self, client):
        client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "AUDIMP01", "name": "Audit Test"}]},
        )
        response = client.get("/api/v1/import/audit")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any(item["import_type"] == "students" for item in data["items"])

    def test_list_filter_import_type(self, client):
        client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "AUDIMP02", "name": "Filter Test"}]},
        )
        response = client.get("/api/v1/import/audit?import_type=students")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert all(item["import_type"] == "students" for item in data["items"])

    def test_list_filter_status(self, client):
        client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "AUDIMP03", "name": "Status Test"}]},
        )
        response = client.get("/api/v1/import/audit?status=completed")
        assert response.status_code == 200
        data = response.json()
        assert all(item["status"] == "completed" for item in data["items"])

    def test_list_pagination(self, client):
        client.post(
            "/api/v1/import/students",
            json={
                "students": [
                    {"usn": "AUDIMP04", "name": "Page Test"},
                    {"usn": "AUDIMP05", "name": "Page Test 2"},
                ]
            },
        )
        response = client.get("/api/v1/import/audit?page=1&page_size=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["page"] == 1
        assert data["page_size"] == 1

    def test_list_newest_first(self, client):
        client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "AUDIMP06", "name": "First"}]},
        )
        client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "AUDIMP07", "name": "Second"}]},
        )
        response = client.get("/api/v1/import/audit")
        data = response.json()
        items = data["items"]
        assert len(items) >= 2
        ids = [item["id"] for item in items]
        assert ids == sorted(ids, reverse=True)

    def test_list_read_only(self, client):
        response = client.post("/api/v1/import/audit")
        assert response.status_code == 405

    def test_list_page_size_limit(self, client):
        response = client.get("/api/v1/import/audit?page_size=200")
        assert response.status_code == 422


class TestAuditLogApiDetail:
    def test_detail_returns_log(self, client):
        client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "AUDIMP08", "name": "Detail Test"}]},
        )
        list_response = client.get("/api/v1/import/audit")
        log_id = list_response.json()["items"][0]["id"]

        response = client.get(f"/api/v1/import/audit/{log_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == log_id
        assert data["import_type"] == "students"
        assert data["status"] == "completed"
        assert data["total_rows"] == 1
        assert data["successful_rows"] == 1
        assert data["started_at"] is not None

    def test_detail_not_found(self, client):
        response = client.get("/api/v1/import/audit/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Audit log not found"

    def test_detail_has_timestamps(self, client):
        client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "AUDIMP09", "name": "Timestamp Test"}]},
        )
        list_response = client.get("/api/v1/import/audit")
        log_id = list_response.json()["items"][0]["id"]

        response = client.get(f"/api/v1/import/audit/{log_id}")
        data = response.json()
        assert data["started_at"] is not None
        assert data["completed_at"] is not None

    def test_detail_has_actor_field(self, client):
        client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "AUDIMP10", "name": "Actor Test"}]},
        )
        list_response = client.get("/api/v1/import/audit")
        log_id = list_response.json()["items"][0]["id"]

        response = client.get(f"/api/v1/import/audit/{log_id}")
        data = response.json()
        assert "actor" in data
        assert data["actor"] is None


class TestAuditIntegration:
    def test_student_import_creates_audit(self, client):
        client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "AUDIMP11", "name": "Audit Student"}]},
        )
        response = client.get("/api/v1/import/audit?import_type=students")
        data = response.json()
        assert data["total"] >= 1
        log = data["items"][0]
        assert log["import_type"] == "students"
        assert log["operation"] == "import"
        assert log["status"] == "completed"
        assert log["total_rows"] == 1
        assert log["successful_rows"] == 1
        assert log["failed_rows"] == 0

    def test_student_import_mixed_creates_correct_audit(self, client):
        client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "AUDIMP12", "name": "Existing"}]},
        )
        client.post(
            "/api/v1/import/students",
            json={
                "students": [
                    {"usn": "AUDIMP12", "name": "Dup"},
                    {"usn": "AUDIMP13", "name": "New"},
                ]
            },
        )
        response = client.get("/api/v1/import/audit?import_type=students")
        data = response.json()
        latest = data["items"][0]
        assert latest["total_rows"] == 2
        assert latest["successful_rows"] == 1
        assert latest["skipped_rows"] == 1
        assert latest["failed_rows"] == 0
        assert latest["status"] == "completed"

    def test_import_behavior_unchanged(self, client):
        response = client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "AUDIMP14", "name": "Unchanged"}]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 1
        assert data["created"] == 1

    def test_audit_preserved_on_row_failure(self, client):
        client.post(
            "/api/v1/import/students",
            json={"students": [{"usn": "AUDIMP15", "name": "Existing"}]},
        )
        client.post(
            "/api/v1/import/students",
            json={
                "students": [
                    {"usn": "AUDIMP15", "name": "Dup"},
                    {"usn": "AUDIMP16", "name": "New"},
                ]
            },
        )
        response = client.get("/api/v1/import/audit?import_type=students")
        data = response.json()
        assert data["total"] >= 1
        log = data["items"][0]
        assert log["status"] in ("completed", "completed_with_errors")
