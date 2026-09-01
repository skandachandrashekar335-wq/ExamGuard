import pytest

from app.models.subject import Subject


class TestSubjectModel:
    def test_create_subject(self, db_session):
        subject = Subject(
            code="CS501",
            name="Machine Learning",
            department="Computer Science",
            semester=5,
            credits=4,
        )
        db_session.add(subject)
        db_session.flush()

        assert subject.id is not None
        assert subject.code == "CS501"
        assert subject.name == "Machine Learning"
        assert subject.department == "Computer Science"
        assert subject.semester == 5
        assert subject.credits == 4
        assert subject.is_active is True

    def test_retrieve_subject(self, db_session):
        subject = Subject(
            code="CS502",
            name="Deep Learning",
            department="Computer Science",
            semester=6,
            credits=3,
        )
        db_session.add(subject)
        db_session.flush()

        retrieved = db_session.query(Subject).filter(Subject.id == subject.id).first()
        assert retrieved is not None
        assert retrieved.code == "CS502"
        assert retrieved.name == "Deep Learning"

    def test_duplicate_code_same_department_rejected(self, db_session):
        subject1 = Subject(
            code="CS501",
            name="Machine Learning",
            department="Computer Science",
            semester=5,
        )
        db_session.add(subject1)
        db_session.flush()

        subject2 = Subject(
            code="CS501",
            name="Advanced ML",
            department="Computer Science",
            semester=7,
        )
        db_session.add(subject2)
        with pytest.raises(Exception):
            db_session.flush()

    def test_same_code_different_department_allowed(self, db_session):
        subject1 = Subject(
            code="CS501",
            name="Machine Learning",
            department="Computer Science",
            semester=5,
        )
        db_session.add(subject1)
        db_session.flush()

        subject2 = Subject(
            code="CS501",
            name="Construction Materials",
            department="Civil Engineering",
            semester=3,
        )
        db_session.add(subject2)
        db_session.flush()

        assert subject1.id != subject2.id

    def test_repr(self, db_session):
        subject = Subject(
            code="CS501",
            name="Machine Learning",
            department="Computer Science",
            semester=5,
        )
        db_session.add(subject)
        db_session.flush()

        repr_str = repr(subject)
        assert "CS501" in repr_str
        assert "Machine Learning" in repr_str

    def test_timestamps_populated(self, db_session):
        subject = Subject(
            code="CS503",
            name="NLP",
            department="Computer Science",
            semester=5,
        )
        db_session.add(subject)
        db_session.flush()

        assert subject.created_at is not None
        assert subject.updated_at is not None

    def test_is_active_defaults_to_true(self, db_session):
        subject = Subject(
            code="CS504",
            name="CV",
            department="Computer Science",
            semester=5,
        )
        db_session.add(subject)
        db_session.flush()

        assert subject.is_active is True

    def test_is_active_can_be_set_false(self, db_session):
        subject = Subject(
            code="CS505",
            name="Robotics",
            department="Computer Science",
            semester=5,
            is_active=False,
        )
        db_session.add(subject)
        db_session.flush()

        assert subject.is_active is False

    def test_credits_nullable(self, db_session):
        subject = Subject(
            code="CS506",
            name="Seminar",
            department="Computer Science",
            semester=5,
            credits=None,
        )
        db_session.add(subject)
        db_session.flush()

        assert subject.credits is None
