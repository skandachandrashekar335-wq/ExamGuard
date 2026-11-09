import pytest
from app.models.chatbot import ChatQueryLog, KnowledgeBaseItem


class TestChatbotModels:
    def test_create_knowledge_item(self, db_session):
        item = KnowledgeBaseItem(
            category="COURSES",
            intent="test_course_intent",
            question="What programs are offered?",
            answer="B.Tech, M.Tech, MCA programs are offered.",
            keywords="btech, mtech, mca, courses",
            is_verified=True,
            requires_admin_confirmation=False,
        )
        db_session.add(item)
        db_session.flush()

        assert item.id is not None
        assert item.category == "COURSES"
        assert item.intent == "test_course_intent"
        assert item.is_active is True
        assert item.created_at is not None
        assert item.updated_at is not None

    def test_duplicate_intent_rejected(self, db_session):
        item1 = KnowledgeBaseItem(
            category="FEES",
            intent="duplicate_intent",
            question="What are the fees?",
            answer="Tuition fees apply.",
            keywords="fees",
        )
        db_session.add(item1)
        db_session.flush()

        item2 = KnowledgeBaseItem(
            category="FEES",
            intent="duplicate_intent",
            question="Another question about fees?",
            answer="Different answer.",
            keywords="fees",
        )
        db_session.add(item2)
        with pytest.raises(Exception):
            db_session.flush()

    def test_chat_query_log_creation(self, db_session):
        log = ChatQueryLog(
            session_id="sess_123",
            query_text="Where is the library located?",
            matched_intent="facilities_campus_overview",
            category="FACILITIES",
            confidence=0.88,
            response_text="The library is in Block B.",
        )
        db_session.add(log)
        db_session.flush()

        assert log.id is not None
        assert log.session_id == "sess_123"
        assert log.confidence == 0.88
        assert log.created_at is not None
