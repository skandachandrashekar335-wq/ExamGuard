import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.import_common import ImportItemResult, ImportStatusResponse, ImportSummary, ImportTypeLimit
from app.services.import_common import IMPORT_LIMITS, count_import_results, process_import_items


class TestProcessImportItems:
    def test_all_succeed(self):
        items = [1, 2, 3]
        process_fn = lambda x: {"value": x * 2, "status": "created"}
        error_fn = lambda x: {"value": x, "status": "failed", "error": "err"}
        results = process_import_items(items, process_fn, error_fn)
        assert len(results) == 3
        assert results[0]["value"] == 2
        assert results[1]["value"] == 4
        assert results[2]["value"] == 6

    def test_some_fail_with_exception(self):
        def process_fn(x):
            if x == 2:
                raise ValueError("bad")
            return {"value": x, "status": "created"}

        error_fn = lambda x: {"value": x, "status": "failed", "error": "Unexpected error"}
        results = process_import_items([1, 2, 3], process_fn, error_fn)
        assert len(results) == 3
        assert results[0]["status"] == "created"
        assert results[1]["status"] == "failed"
        assert results[1]["error"] == "Unexpected error"
        assert results[2]["status"] == "created"

    def test_empty_items(self):
        results = process_import_items([], lambda x: x, lambda x: x)
        assert results == []

    def test_all_fail(self):
        def process_fn(x):
            raise RuntimeError("boom")

        error_fn = lambda x: {"status": "failed"}
        results = process_import_items([1, 2], process_fn, error_fn)
        assert len(results) == 2
        assert all(r["status"] == "failed" for r in results)

    def test_preserves_return_type(self):
        class FakeResult:
            def __init__(self, val, status):
                self.val = val
                self.status = status

        items = [1, 2]
        process_fn = lambda x: FakeResult(x, "created")
        error_fn = lambda x: FakeResult(x, "failed")
        results = process_import_items(items, process_fn, error_fn)
        assert all(isinstance(r, FakeResult) for r in results)


class TestCountImportResults:
    def test_count_mixed(self):
        class MockResult:
            def __init__(self, status):
                self.status = status

        results = [
            MockResult("created"),
            MockResult("skipped"),
            MockResult("created"),
            MockResult("failed"),
        ]
        counts = count_import_results(results)
        assert counts == {"created": 2, "skipped": 1, "failed": 1}

    def test_count_empty(self):
        counts = count_import_results([])
        assert counts == {}

    def test_count_single_status(self):
        class MockResult:
            def __init__(self, status):
                self.status = status

        results = [MockResult("assigned"), MockResult("assigned")]
        counts = count_import_results(results)
        assert counts == {"assigned": 2}

    def test_count_cancelled(self):
        class MockResult:
            def __init__(self, status):
                self.status = status

        results = [
            MockResult("cancelled"),
            MockResult("cancelled"),
            MockResult("skipped"),
        ]
        counts = count_import_results(results)
        assert counts == {"cancelled": 2, "skipped": 1}


class TestImportSummarySchema:
    def test_import_summary_fields(self):
        summary = ImportSummary(total=10, created=7, skipped=2, failed=1)
        assert summary.total == 10
        assert summary.created == 7
        assert summary.skipped == 2
        assert summary.failed == 1

    def test_import_item_result_fields(self):
        result = ImportItemResult(status="created")
        assert result.status == "created"
        assert result.error is None

    def test_import_item_result_with_error(self):
        result = ImportItemResult(status="failed", error="boom")
        assert result.error == "boom"


class TestImportTypeLimitSchema:
    def test_import_type_limit(self):
        limit = ImportTypeLimit(import_type="students", max_items=500)
        assert limit.import_type == "students"
        assert limit.max_items == 500


class TestImportStatusResponseSchema:
    def test_import_status_response(self):
        resp = ImportStatusResponse(
            import_types=[
                ImportTypeLimit(import_type="students", max_items=500),
            ]
        )
        assert len(resp.import_types) == 1
        assert resp.import_types[0].import_type == "students"


class TestImportLimits:
    def test_limits_defined(self):
        assert "students" in IMPORT_LIMITS
        assert "subjects" in IMPORT_LIMITS
        assert "exams" in IMPORT_LIMITS
        assert "registrations" in IMPORT_LIMITS
        assert "registration_cancellations" in IMPORT_LIMITS
        assert "seat_assignments" in IMPORT_LIMITS
        assert "seat_assignment_cancellations" in IMPORT_LIMITS

    def test_limits_are_positive(self):
        for k, v in IMPORT_LIMITS.items():
            assert v > 0, f"Limit for {k} must be positive"

    def test_limit_count(self):
        assert len(IMPORT_LIMITS) == 7


class TestImportStatusEndpoint:
    @pytest.fixture()
    def client(self):
        return TestClient(app)

    def test_status_endpoint_succeeds(self, client):
        response = client.get("/api/v1/import/status")
        assert response.status_code == 200

    def test_expected_import_types_present(self, client):
        response = client.get("/api/v1/import/status")
        data = response.json()
        types = {t["import_type"] for t in data["import_types"]}
        expected = {
            "students",
            "subjects",
            "exams",
            "registrations",
            "registration_cancellations",
            "seat_assignments",
            "seat_assignment_cancellations",
        }
        assert types == expected

    def test_limits_are_correct(self, client):
        response = client.get("/api/v1/import/status")
        data = response.json()
        limits = {t["import_type"]: t["max_items"] for t in data["import_types"]}
        assert limits["students"] == 500
        assert limits["subjects"] == 200
        assert limits["exams"] == 500
        assert limits["registrations"] == 500
        assert limits["registration_cancellations"] == 500
        assert limits["seat_assignments"] == 200
        assert limits["seat_assignment_cancellations"] == 200

    def test_endpoint_is_read_only(self, client):
        response = client.post("/api/v1/import/status")
        assert response.status_code == 405

    def test_endpoint_returns_all_types(self, client):
        response = client.get("/api/v1/import/status")
        data = response.json()
        assert len(data["import_types"]) == 7
