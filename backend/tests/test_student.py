import pytest
from sqlalchemy.exc import IntegrityError

from app.models.student import Student


class TestStudentModel:
    def test_create_student(self, db_session):
        student = Student(usn="TEST001", name="Test Student Alpha")
        db_session.add(student)
        db_session.commit()

        assert student.id is not None
        assert student.usn == "TEST001"
        assert student.name == "Test Student Alpha"
        assert student.is_active is True
        assert student.created_at is not None
        assert student.updated_at is not None

    def test_retrieve_student(self, db_session):
        student = Student(usn="TEST002", name="Test Student Beta")
        db_session.add(student)
        db_session.commit()

        retrieved = db_session.query(Student).filter_by(usn="TEST002").one()
        assert retrieved.name == "Test Student Beta"
        assert retrieved.id == student.id

    def test_duplicate_usn_rejected(self, db_session):
        s1 = Student(usn="DUP001", name="First Student")
        s2 = Student(usn="DUP001", name="Second Student")
        db_session.add(s1)
        db_session.commit()

        db_session.add(s2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_usn_is_unique_constraint(self, db_session):
        students = db_session.query(Student).filter_by(usn="UNIQUE001").all()
        assert len(students) == 0

    def test_repr(self, db_session):
        student = Student(usn="REPR001", name="Repr Student")
        db_session.add(student)
        db_session.commit()

        repr_str = repr(student)
        assert "REPR001" in repr_str
        assert "Repr Student" in repr_str

    def test_timestamps_populated(self, db_session):
        student = Student(usn="TS001", name="Timestamp Student")
        db_session.add(student)
        db_session.commit()

        assert student.created_at is not None
        assert student.updated_at is not None

    def test_is_active_defaults_to_true(self, db_session):
        student = Student(usn="ACT001", name="Active Student")
        db_session.add(student)
        db_session.commit()

        assert student.is_active is True

    def test_is_active_can_be_set_false(self, db_session):
        student = Student(usn="ACT002", name="Inactive Student", is_active=False)
        db_session.add(student)
        db_session.commit()

        assert student.is_active is False
