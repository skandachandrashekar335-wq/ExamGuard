"""Verify real Chatbot knowledge-base ingestion, source persistence,
intent retrieval, and safe fallback on real PostgreSQL.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.chatbot import KnowledgeBaseItem, ChatQueryLog
from app.services.chatbot import seed_knowledge_base_if_empty, process_chat_query

DB_URL = "postgresql://skandachandrashekar335@localhost:5432/examguard_test_real"

def run_chatbot_verification():
    print("=== Chatbot Knowledge-Base & Retrieval Verification ===")
    engine = create_engine(DB_URL)
    SessionClass = sessionmaker(bind=engine)
    db = SessionClass()

    # 1. Ingestion of verified institutional facts
    print("\n[1] Ingesting verified institutional knowledge base into PostgreSQL...")
    seed_count = seed_knowledge_base_if_empty(db)
    print(f"  Knowledge items seeded/verified in DB: {seed_count}")

    # Query items to verify metadata persistence
    kb_items = db.query(KnowledgeBaseItem).all()
    print(f"  Total persisted knowledge items in PostgreSQL: {len(kb_items)}")
    for item in kb_items[:3]:
        print(f"    - [{item.category}] {item.intent}: requires_admin_confirmation={item.requires_admin_confirmation}, verified={item.is_verified}")

    # 2. Supported category query (Fees) - Should require admin confirmation
    print("\n[2] Testing query for Fees (requires admin confirmation)...")
    resp_fees = process_chat_query(db, "What is the tuition fee structure for computer science?", session_id="test-session-001")
    print(f"  Matched Intent: {resp_fees.intent}")
    print(f"  Category:       {resp_fees.category}")
    print(f"  Confidence:     {resp_fees.confidence:.2f}")
    print(f"  Requires Admin Confirmation: {resp_fees.requires_admin_confirmation}")
    print(f"  Answer Snippet: {resp_fees.answer[:120]}...")
    assert resp_fees.category == "FEES"
    assert resp_fees.requires_admin_confirmation is True

    # 3. Supported category query (Admissions)
    print("\n[3] Testing query for Admissions...")
    resp_adm = process_chat_query(db, "What documents do I need to bring for admission verification?", session_id="test-session-001")
    print(f"  Matched Intent: {resp_adm.intent}")
    print(f"  Category:       {resp_adm.category}")
    print(f"  Confidence:     {resp_adm.confidence:.2f}")
    assert resp_adm.category == "DOCUMENTS"

    # 4. Out-of-scope unsupported query -> Safe fallback
    print("\n[4] Testing unsupported out-of-scope query...")
    resp_fallback = process_chat_query(db, "Can you order me a pizza and a burger to the examination hall?", session_id="test-session-001")
    print(f"  Matched Intent: {resp_fallback.intent}")
    print(f"  Matched Flag:   {resp_fallback.matched}")
    print(f"  Confidence:     {resp_fallback.confidence:.2f}")
    print(f"  Answer:         {resp_fallback.answer}")
    assert not resp_fallback.matched
    assert "admissions@dscasc.edu.in" in resp_fallback.answer or "support team" in resp_fallback.answer

    # 5. Verify query audit logging in PostgreSQL
    print("\n[5] Verifying persistent query audit logs in PostgreSQL...")
    logs = db.query(ChatQueryLog).filter_by(session_id="test-session-001").all()
    print(f"  Audit logs recorded for session: {len(logs)}")
    assert len(logs) >= 3
    for log in logs:
        print(f"    - Query: '{log.query_text[:30]}...' -> Intent: {log.matched_intent}, Conf: {log.confidence:.2f}")

    db.close()
    engine.dispose()
    print("\nALL CHATBOT INGESTION & RETRIEVAL VERIFICATIONS PASSED.")

if __name__ == "__main__":
    run_chatbot_verification()
