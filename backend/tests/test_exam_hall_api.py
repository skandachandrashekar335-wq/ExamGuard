import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.exam_hall import ExamHall


@pytest.fixture(autouse=True)
def clean_test_halls():
    """Remove test halls before each test to avoid conflicts."""
    db = SessionLocal()
    try:
        test_prefixes = ("HALL", "BLD", "RM", "FILT", "SRCH", "DEL", "UPD", "DUP", "DIM", "TRM", "SCR")
        for prefix in test_prefixes:
            db.execute(
                delete(ExamHall).where(ExamHall.building.ilike(f"{prefix}%"))
            )
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


class TestExamHallAPI:
    def test_create_hall(self, client):
        response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "HALL Block A",
                "room_number": "HALL101",
                "name": "Main Auditorium",
                "capacity": 120,
                "rows": 10,
                "columns": 12,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["building"] == "HALL Block A"
        assert data["room_number"] == "HALL101"
        assert data["name"] == "Main Auditorium"
        assert data["capacity"] == 120
        assert data["rows"] == 10
        assert data["columns"] == 12
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data

    def test_create_hall_minimal(self, client):
        response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "HALL Block B",
                "room_number": "HALL201",
                "capacity": 60,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] is None
        assert data["rows"] is None
        assert data["columns"] is None

    def test_get_hall(self, client):
        create = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "HALL Block C",
                "room_number": "HALL301",
                "capacity": 80,
            },
        )
        hall_id = create.json()["id"]

        response = client.get(f"/api/v1/exam-halls/{hall_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == hall_id
        assert data["building"] == "HALL Block C"
        assert data["room_number"] == "HALL301"

    def test_get_hall_not_found(self, client):
        response = client.get("/api/v1/exam-halls/999999")
        assert response.status_code == 404

    def test_list_halls(self, client):
        client.post(
            "/api/v1/exam-halls",
            json={
                "building": "HALL List A",
                "room_number": "HALL301",
                "capacity": 50,
            },
        )
        client.post(
            "/api/v1/exam-halls",
            json={
                "building": "HALL List A",
                "room_number": "HALL302",
                "capacity": 60,
            },
        )
        response = client.get("/api/v1/exam-halls")
        assert response.status_code == 200
        assert response.json()["total"] >= 2

    def test_pagination(self, client):
        for i in range(5):
            client.post(
                "/api/v1/exam-halls",
                json={
                    "building": "HALL Page",
                    "room_number": f"HALL{i + 1:03d}",
                    "capacity": 40 + i,
                },
            )

        response = client.get("/api/v1/exam-halls?page=1&page_size=2")
        data = response.json()
        assert len(data["items"]) <= 2
        assert data["page"] == 1
        assert data["page_size"] == 2

    def test_search_by_building(self, client):
        client.post(
            "/api/v1/exam-halls",
            json={
                "building": "SRCH Building Alpha",
                "room_number": "SRCH001",
                "capacity": 50,
            },
        )
        response = client.get("/api/v1/exam-halls?search=Building+Alpha")
        data = response.json()
        assert any(
            h["building"] == "SRCH Building Alpha" for h in data["items"]
        )

    def test_search_by_room_number(self, client):
        client.post(
            "/api/v1/exam-halls",
            json={
                "building": "SRCH Room",
                "room_number": "SRCHUnique",
                "capacity": 50,
            },
        )
        response = client.get("/api/v1/exam-halls?search=SRCHUnique")
        data = response.json()
        assert any(
            h["room_number"] == "SRCHUnique" for h in data["items"]
        )

    def test_search_by_name(self, client):
        client.post(
            "/api/v1/exam-halls",
            json={
                "building": "FILT Block",
                "room_number": "FILT101",
                "name": "Grand Hall XYZ",
                "capacity": 200,
            },
        )
        response = client.get("/api/v1/exam-halls?search=Grand+Hall+XYZ")
        data = response.json()
        assert any(h["name"] == "Grand Hall XYZ" for h in data["items"])

    def test_duplicate_hall_rejected(self, client):
        client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DUP Block",
                "room_number": "DUP101",
                "capacity": 50,
            },
        )
        response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DUP Block",
                "room_number": "DUP101",
                "capacity": 60,
            },
        )
        assert response.status_code == 409

    def test_same_room_different_building_allowed(self, client):
        client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DUP Block X",
                "room_number": "DUP101",
                "capacity": 50,
            },
        )
        response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DUP Block Y",
                "room_number": "DUP101",
                "capacity": 50,
            },
        )
        assert response.status_code == 201

    def test_same_building_different_room_allowed(self, client):
        client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DUP Block Z",
                "room_number": "DUP101",
                "capacity": 50,
            },
        )
        response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DUP Block Z",
                "room_number": "DUP102",
                "capacity": 50,
            },
        )
        assert response.status_code == 201

    def test_empty_building_rejected(self, client):
        response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "",
                "room_number": "HALL101",
                "capacity": 50,
            },
        )
        assert response.status_code == 422

    def test_empty_room_number_rejected(self, client):
        response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "HALL Block",
                "room_number": "",
                "capacity": 50,
            },
        )
        assert response.status_code == 422

    def test_zero_capacity_rejected(self, client):
        response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "HALL Block",
                "room_number": "HALL101",
                "capacity": 0,
            },
        )
        assert response.status_code == 422

    def test_negative_capacity_rejected(self, client):
        response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "HALL Block",
                "room_number": "HALL101",
                "capacity": -5,
            },
        )
        assert response.status_code == 422

    def test_invalid_rows_rejected(self, client):
        response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DIM Block",
                "room_number": "DIM001",
                "capacity": 50,
                "rows": 0,
                "columns": 10,
            },
        )
        assert response.status_code == 422

    def test_invalid_columns_rejected(self, client):
        response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DIM Block",
                "room_number": "DIM002",
                "capacity": 50,
                "rows": 10,
                "columns": 0,
            },
        )
        assert response.status_code == 422

    def test_negative_rows_rejected(self, client):
        response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DIM Block",
                "room_number": "DIM003",
                "capacity": 50,
                "rows": -3,
                "columns": 10,
            },
        )
        assert response.status_code == 422

    def test_negative_columns_rejected(self, client):
        response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DIM Block",
                "room_number": "DIM004",
                "capacity": 50,
                "rows": 10,
                "columns": -2,
            },
        )
        assert response.status_code == 422

    def test_rows_columns_less_than_capacity_rejected(self, client):
        response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DIM Block",
                "room_number": "DIM005",
                "capacity": 100,
                "rows": 5,
                "columns": 5,
            },
        )
        assert response.status_code == 422

    def test_rows_columns_equal_capacity_allowed(self, client):
        response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DIM Block",
                "room_number": "DIM006",
                "capacity": 25,
                "rows": 5,
                "columns": 5,
            },
        )
        assert response.status_code == 201

    def test_rows_columns_greater_than_capacity_allowed(self, client):
        response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DIM Block",
                "room_number": "DIM007",
                "capacity": 20,
                "rows": 5,
                "columns": 5,
            },
        )
        assert response.status_code == 201

    def test_rows_only_allowed(self, client):
        response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DIM Block",
                "room_number": "DIM008",
                "capacity": 50,
                "rows": 10,
            },
        )
        assert response.status_code == 201

    def test_columns_only_allowed(self, client):
        response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DIM Block",
                "room_number": "DIM009",
                "capacity": 50,
                "columns": 10,
            },
        )
        assert response.status_code == 201

    def test_whitespace_trimming(self, client):
        response = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "  TRM Building  ",
                "room_number": "  TRM101  ",
                "name": "  Trimmed Hall  ",
                "capacity": 50,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["building"] == "TRM Building"
        assert data["room_number"] == "TRM101"
        assert data["name"] == "Trimmed Hall"

    def test_update_hall(self, client):
        create = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "UPD Block",
                "room_number": "UPD101",
                "capacity": 50,
            },
        )
        hall_id = create.json()["id"]

        response = client.patch(
            f"/api/v1/exam-halls/{hall_id}",
            json={"name": "Updated Hall Name"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Hall Name"

    def test_update_hall_capacity(self, client):
        create = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "UPD Block",
                "room_number": "UPD102",
                "capacity": 50,
            },
        )
        hall_id = create.json()["id"]

        response = client.patch(
            f"/api/v1/exam-halls/{hall_id}",
            json={"capacity": 100},
        )
        assert response.status_code == 200
        assert response.json()["capacity"] == 100

    def test_update_hall_not_found(self, client):
        response = client.patch(
            "/api/v1/exam-halls/999999",
            json={"name": "Updated"},
        )
        assert response.status_code == 404

    def test_update_duplicate_rejected(self, client):
        client.post(
            "/api/v1/exam-halls",
            json={
                "building": "UPD Block",
                "room_number": "UPD103",
                "capacity": 50,
            },
        )
        create2 = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "UPD Block",
                "room_number": "UPD104",
                "capacity": 50,
            },
        )
        hall2_id = create2.json()["id"]

        response = client.patch(
            f"/api/v1/exam-halls/{hall2_id}",
            json={"room_number": "UPD103"},
        )
        assert response.status_code == 409

    def test_soft_delete(self, client):
        create = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DEL Block",
                "room_number": "DEL101",
                "capacity": 50,
            },
        )
        hall_id = create.json()["id"]

        response = client.delete(f"/api/v1/exam-halls/{hall_id}")
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_deleted_hall_hidden_from_list(self, client):
        create = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DEL Block",
                "room_number": "DEL102",
                "capacity": 50,
            },
        )
        hall_id = create.json()["id"]
        client.delete(f"/api/v1/exam-halls/{hall_id}")

        response = client.get("/api/v1/exam-halls")
        data = response.json()
        assert not any(h["id"] == hall_id for h in data["items"])

    def test_deleted_hall_visible_with_include_inactive(self, client):
        create = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DEL Block",
                "room_number": "DEL103",
                "capacity": 50,
            },
        )
        hall_id = create.json()["id"]
        client.delete(f"/api/v1/exam-halls/{hall_id}")

        response = client.get("/api/v1/exam-halls?include_inactive=true")
        data = response.json()
        assert any(h["id"] == hall_id for h in data["items"])

    def test_get_deleted_hall(self, client):
        create = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DEL Block",
                "room_number": "DEL104",
                "capacity": 50,
            },
        )
        hall_id = create.json()["id"]
        client.delete(f"/api/v1/exam-halls/{hall_id}")

        response = client.get(f"/api/v1/exam-halls/{hall_id}")
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_delete_nonexistent(self, client):
        response = client.delete("/api/v1/exam-halls/999999")
        assert response.status_code == 404

    def test_missing_required_fields(self, client):
        response = client.post("/api/v1/exam-halls", json={"building": "Test"})
        assert response.status_code == 422

    def test_database_uniqueness_enforcement(self, client):
        response1 = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DUP Block",
                "room_number": "DUP101",
                "capacity": 50,
            },
        )
        assert response1.status_code == 201

        response2 = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "DUP Block",
                "room_number": "DUP101",
                "capacity": 75,
            },
        )
        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"]

    def test_update_whitespace_trimming(self, client):
        create = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "TRM Block",
                "room_number": "TRM101",
                "capacity": 50,
            },
        )
        hall_id = create.json()["id"]

        response = client.patch(
            f"/api/v1/exam-halls/{hall_id}",
            json={"building": "  TRM Block Updated  "},
        )
        assert response.status_code == 200
        assert response.json()["building"] == "TRM Block Updated"

    def test_hall_exists_in_database(self, client):
        from app.models.exam_hall import ExamHall
        from sqlalchemy import text

        create = client.post(
            "/api/v1/exam-halls",
            json={
                "building": "SCR Block",
                "room_number": "SCR101",
                "name": "Screened Hall",
                "capacity": 80,
                "rows": 8,
                "columns": 10,
            },
        )
        assert create.status_code == 201
        hall_id = create.json()["id"]

        db = SessionLocal()
        try:
            hall = db.query(ExamHall).filter(ExamHall.id == hall_id).first()
            assert hall is not None
            assert hall.building == "SCR Block"
            assert hall.room_number == "SCR101"
            assert hall.name == "Screened Hall"
            assert hall.capacity == 80
            assert hall.rows == 8
            assert hall.columns == 10
            assert hall.is_active is True
        finally:
            db.close()
