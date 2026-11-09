"""Verify authentication, Firebase token exchange rules, invalid/expired token rejection,
role assignment, and exam-scoped invigilator RBAC.
"""

import os
from datetime import datetime, timezone, timedelta, time
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import create_app
from app.auth import create_access_token, decode_token, Role
from app.models.user import User
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.subject import Subject
from app.models.invigilator_assignment import InvigilatorAssignment
from app.core.config import get_settings

DB_URL = "postgresql://skandachandrashekar335@localhost:5432/examguard_test_real"

def run_auth_verification():
    print("=== Authentication & RBAC Verification ===")
    os.environ["DATABASE_URL"] = DB_URL
    
    engine = create_engine(DB_URL)
    SessionClass = sessionmaker(bind=engine)
    
    import app.core.database as db_module
    db_module.engine = engine
    db_module.SessionLocal = SessionClass

    app = create_app()
    client = TestClient(app)

    # 1. Test live Firebase endpoint rejecting invalid token
    print("\n[1] Testing invalid Firebase token rejection via live endpoint...")
    resp = client.post(
        "/api/v1/auth/firebase/exchange",
        headers={"Authorization": "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature"},
    )
    print(f"  Invalid Token HTTP Status: {resp.status_code}")
    print(f"  Response Detail: {resp.json().get('detail')}")
    assert resp.status_code == 401
    assert "Firebase token verification failed" in resp.json()["detail"]

    # 2. Test live Firebase endpoint rejecting expired token
    print("\n[2] Testing expired Firebase token format rejection...")
    # Simulated expired format
    expired_token = "eyJhbGciOiJSUzI1NiJ9.eyJleHAiOjE1MDAwMDAwMDB9.expired_sig"
    resp_exp = client.post(
        "/api/v1/auth/firebase/exchange",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    print(f"  Expired Token HTTP Status: {resp_exp.status_code}")
    print(f"  Response Detail: {resp_exp.json().get('detail')}")
    assert resp_exp.status_code == 401

    # 3. Test Backend JWT Token Issuance & Expiration
    print("\n[3] Testing Backend JWT creation, decoding, and expiration...")
    valid_payload = {"sub": "1", "email": "admin@examguard.edu", "role": Role.ADMIN}
    token = create_access_token(valid_payload, expires_delta=timedelta(minutes=15))
    claims = decode_token(token)
    assert claims is not None
    assert claims["email"] == "admin@examguard.edu"
    assert claims["role"] == Role.ADMIN
    print(f"  Valid token decoded: sub={claims['sub']}, role={claims['role']}")

    expired_jwt = create_access_token(valid_payload, expires_delta=timedelta(seconds=-10))
    expired_claims = decode_token(expired_jwt)
    assert expired_claims is None
    print("  Expired token successfully rejected by decode_token() (returned None).")

    # 4. Role Assignment & Exam-Scoped Invigilator Authorization in PostgreSQL
    print("\n[4] Testing Role Assignment & Exam-Scoped Invigilator Authorization...")
    engine = create_engine(DB_URL)
    SessionClass = sessionmaker(bind=engine)
    db = SessionClass()

    now = datetime.now(timezone.utc)
    today = now.date()

    # Create Invigilator User
    inv_email = f"invigilator.{int(now.timestamp())}@examguard.edu"
    invigilator_user = User(
        email=inv_email,
        full_name="Assigned Test Invigilator",
        role=Role.REVIEWER,  # Base account role is REVIEWER
        is_active=True,
    )
    db.add(invigilator_user)
    db.flush()

    # Create 2 Exams
    subj = db.query(Subject).first()
    t_sec = int(now.timestamp()) % 1000
    exam_assigned = Exam(
        subject_id=subj.id,
        exam_name=f"Assigned Scope Exam {t_sec}",
        exam_date=today,
        start_time=time(t_sec // 3600 % 12, t_sec // 60 % 60, t_sec % 60),
        end_time=time((t_sec // 3600 + 3) % 24, t_sec // 60 % 60, t_sec % 60),
        semester=6,
        department="Computer Science",
    )
    exam_forbidden = Exam(
        subject_id=subj.id,
        exam_name=f"Unassigned Forbidden Exam {t_sec}",
        exam_date=today,
        start_time=time((t_sec // 3600 + 4) % 24, t_sec // 60 % 60, t_sec % 60),
        end_time=time((t_sec // 3600 + 7) % 24, t_sec // 60 % 60, t_sec % 60),
        semester=6,
        department="Computer Science",
    )
    db.add_all([exam_assigned, exam_forbidden])
    db.flush()

    # Assign invigilator ONLY to exam_assigned
    hall = db.query(ExamHall).first()
    assignment = InvigilatorAssignment(
        user_id=invigilator_user.id,
        exam_id=exam_assigned.id,
        exam_hall_id=hall.id,
    )
    db.add(assignment)
    db.commit()

    # Create Invigilator JWT
    inv_token = create_access_token({
        "sub": str(invigilator_user.id),
        "email": invigilator_user.email,
        "role": Role.REVIEWER,
    })

    # Test access to invigilator profile for assigned user
    resp_assigned = client.get(
        "/api/v1/invigilator/my-assignment",
        headers={"Authorization": f"Bearer {inv_token}"},
    )
    print(f"  Assigned User /my-assignment HTTP Status: {resp_assigned.status_code}")
    assert resp_assigned.status_code == 200, f"Expected 200, got {resp_assigned.status_code}: {resp_assigned.text}"
    assignment_data = resp_assigned.json()
    print(f"  Assignment detected: exam_name='{assignment_data.get('exam_name')}', status='{assignment_data.get('assignment_status')}', role='{assignment_data.get('account_role')}'")
    assert assignment_data.get("exam_name") == exam_assigned.exam_name
    assert assignment_data.get("assignment_status") == "SCHEDULED"
    assert assignment_data.get("account_role") == Role.REVIEWER

    # Test an unassigned reviewer calling protected invigilator profile
    unassigned_user = User(
        email=f"unassigned.{int(now.timestamp())}@examguard.edu",
        full_name="Unassigned Reviewer",
        role=Role.REVIEWER,
        is_active=True,
    )
    db.add(unassigned_user)
    db.commit()

    unassigned_token = create_access_token({
        "sub": str(unassigned_user.id),
        "email": unassigned_user.email,
        "role": Role.REVIEWER,
    })

    resp_unassigned = client.get(
        "/api/v1/invigilator/profile",
        headers={"Authorization": f"Bearer {unassigned_token}"},
    )
    print(f"  Unassigned User Protected /profile HTTP Status: {resp_unassigned.status_code}")
    print(f"  Unassigned Detail: {resp_unassigned.json().get('detail')}")
    assert resp_unassigned.status_code == 403, f"Expected 403 Forbidden, got {resp_unassigned.status_code}"

    db.close()
    engine.dispose()
    print("ALL AUTHENTICATION & RBAC TESTS PASSED.")

if __name__ == "__main__":
    run_auth_verification()
