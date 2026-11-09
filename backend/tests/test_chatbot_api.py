import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.auth import Role, get_current_user
from app.core.database import SessionLocal
from app.main import app
from app.models.chatbot import ChatQueryLog, KnowledgeBaseItem


@pytest.fixture(autouse=True)
def clean_test_chatbot_data():
    db = SessionLocal()
    try:
        db.execute(delete(ChatQueryLog))
        db.execute(delete(KnowledgeBaseItem).where(KnowledgeBaseItem.intent.like("api_test_%")))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


class TestChatbotAPI:
    def test_query_endpoint_happy_path(self, client):
        resp = client.post(
            "/api/v1/chatbot/query",
            json={"query": "What are the eligibility requirements for admission?", "session_id": "test_s1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched"] is True
        assert data["category"] == "ELIGIBILITY"
        assert "confidence" in data
        assert isinstance(data["suggestions"], list)

    def test_query_endpoint_fallback(self, client):
        resp = client.post(
            "/api/v1/chatbot/query",
            json={"query": "What is the distance to Mars in kilometers?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched"] is False
        assert data["intent"] == "fallback_unknown_intent"
        assert "admissions@college.edu" in data["answer"]

    def test_query_endpoint_empty_query_rejected(self, client):
        resp = client.post("/api/v1/chatbot/query", json={"query": "   "})
        assert resp.status_code == 422

    def test_get_categories(self, client):
        resp = client.get("/api/v1/chatbot/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        assert len(data["categories"]) == 9

    def test_get_suggestions(self, client):
        resp = client.get("/api/v1/chatbot/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert "suggestions" in data
        assert len(data["suggestions"]) > 5

    def test_admin_knowledge_crud(self, client):
        # Create knowledge item as admin
        create_payload = {
            "category": "FACILITIES",
            "intent": "api_test_wifi_access",
            "question": "How do students access campus Wi-Fi?",
            "answer": "Students receive login credentials for the 'Student-Secure' Wi-Fi during orientation.",
            "keywords": "wifi, internet, login credentials, network",
            "is_verified": True,
            "requires_admin_confirmation": False,
        }
        create_resp = client.post("/api/v1/chatbot/knowledge", json=create_payload)
        assert create_resp.status_code == 201
        item_id = create_resp.json()["id"]

        # List
        list_resp = client.get("/api/v1/chatbot/knowledge?search=wifi")
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] >= 1

        # Update
        patch_resp = client.patch(
            f"/api/v1/chatbot/knowledge/{item_id}",
            json={"answer": "Wi-Fi credentials are provided via student portal."},
        )
        assert patch_resp.status_code == 200
        assert "student portal" in patch_resp.json()["answer"]

        # Delete (soft delete)
        del_resp = client.delete(f"/api/v1/chatbot/knowledge/{item_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["is_active"] is False

    def test_reviewer_cannot_modify_knowledge(self, client):
        def _reviewer_user():
            return {"sub": "99", "role": Role.REVIEWER, "email": "rev@example.com"}

        app.dependency_overrides[get_current_user] = _reviewer_user
        try:
            resp = client.post(
                "/api/v1/chatbot/knowledge",
                json={
                    "category": "GENERAL",
                    "intent": "api_test_unauthorized",
                    "question": "Will this succeed?",
                    "answer": "No, reviewer should be forbidden.",
                },
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)
