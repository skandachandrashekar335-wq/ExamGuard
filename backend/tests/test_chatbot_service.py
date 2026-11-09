import pytest
from app.schemas.chatbot import KnowledgeBaseItemCreate, KnowledgeBaseItemUpdate
from app.services import chatbot as chatbot_service


class TestChatbotService:
    def test_seed_knowledge_base(self, db_session):
        count = chatbot_service.seed_knowledge_base_if_empty(db_session)
        assert count >= len(chatbot_service.DEFAULT_KNOWLEDGE_BASE)
        # Calling again should be idempotent
        assert chatbot_service.seed_knowledge_base_if_empty(db_session) == count

    @pytest.mark.parametrize(
        "query,expected_category,expected_intent_substring",
        [
            ("What undergraduate engineering courses are available?", "COURSES", "courses"),
            ("What is the admission procedure for B.Tech programs?", "ADMISSIONS", "admissions"),
            ("What are the minimum eligibility marks for 12th PUC?", "ELIGIBILITY", "eligibility"),
            ("What is the tuition fee structure and how do I pay?", "FEES", "fees"),
            ("What documents and original certificates do I need to bring for admission?", "DOCUMENTS", "documents"),
            ("What are the examination rules and hall ticket requirements under ExamGuard?", "EXAMINATIONS", "exam"),
            ("Where can I check the exam timetable and internal schedule?", "TIMETABLES", "timetables"),
            ("Tell me about the campus library, hostel, and sports facilities.", "FACILITIES", "facilities"),
            ("What are the college working hours and admission office phone number?", "GENERAL", "general"),
        ],
    )
    def test_supported_category_queries(self, db_session, query, expected_category, expected_intent_substring):
        chatbot_service.seed_knowledge_base_if_empty(db_session)
        res = chatbot_service.process_chat_query(db_session, query)

        assert res.matched is True
        assert res.category == expected_category
        assert expected_intent_substring in res.intent
        assert res.confidence >= 0.35
        assert len(res.answer) > 20
        assert len(res.suggestions) > 0

    def test_fuzzy_matching_with_typos(self, db_session):
        chatbot_service.seed_knowledge_base_if_empty(db_session)
        # Typo: "fee sturcture" instead of "fee structure"
        res = chatbot_service.process_chat_query(db_session, "fee sturcture payment")
        assert res.matched is True
        assert res.category == "FEES"

    @pytest.mark.parametrize(
        "unsupported_query",
        [
            "Can you order me a pepperoni pizza right now?",
            "What is the MBBS anatomy syllabus for first year medical students?",
            "Can I get a 100% free crypto token scholarship?",
            "Who won the 2024 ICC T20 cricket world cup?",
        ],
    )
    def test_unsupported_out_of_scope_query_triggers_safe_fallback(self, db_session, unsupported_query):
        chatbot_service.seed_knowledge_base_if_empty(db_session)
        res = chatbot_service.process_chat_query(db_session, unsupported_query)

        assert res.matched is False
        assert res.intent == "fallback_unknown_intent"
        assert "I don't have verified institutional information" in res.answer
        assert "admissions@college.edu" in res.answer
        assert len(res.suggestions) > 0
        assert res.requires_admin_confirmation is True

    def test_category_list(self):
        categories_resp = chatbot_service.list_categories()
        assert len(categories_resp.categories) == 9
        names = [c.name for c in categories_resp.categories]
        assert "COURSES" in names
        assert "FEES" in names
        assert "EXAMINATIONS" in names

    def test_admin_crud_knowledge_item(self, db_session):
        create_data = KnowledgeBaseItemCreate(
            category="GENERAL",
            intent="transport_bus_routes",
            question="Are college buses available across the city?",
            answer="Yes, college buses operate on 15 designated routes across the city.",
            keywords="transport, bus, route, pick up, travel",
            is_verified=True,
            requires_admin_confirmation=False,
        )
        item = chatbot_service.create_knowledge_item(db_session, create_data)
        assert item.id is not None
        assert item.intent == "transport_bus_routes"

        # Update
        update_data = KnowledgeBaseItemUpdate(
            answer="Yes, college buses operate on 18 designated routes.",
        )
        updated = chatbot_service.update_knowledge_item(db_session, item.id, update_data)
        assert "18 designated routes" in updated.answer

        # Query should match new knowledge item
        res = chatbot_service.process_chat_query(db_session, "Are there college buses for transport?")
        assert res.matched is True
        assert res.intent == "transport_bus_routes"
        assert "18 designated routes" in res.answer

        # Deactivate
        deactivated = chatbot_service.deactivate_knowledge_item(db_session, item.id)
        assert deactivated.is_active is False
