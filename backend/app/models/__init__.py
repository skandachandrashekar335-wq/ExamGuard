from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.student import Student  # noqa: E402, F401
from app.models.document import Document  # noqa: E402, F401
from app.models.extraction import ExtractionResult, ExtractedField  # noqa: E402, F401
from app.models.subject import Subject  # noqa: E402, F401
from app.models.exam import Exam  # noqa: E402, F401
from app.models.exam_hall import ExamHall  # noqa: E402, F401
from app.models.exam_registration import ExamRegistration  # noqa: E402, F401
from app.models.seat_assignment import SeatAssignment  # noqa: E402, F401
from app.models.hall_ticket_match import HallTicketMatchResult, HallTicketMatchSignal  # noqa: E402, F401
from app.models.verification import VerificationOutcome  # noqa: E402, F401
from app.models.import_audit_log import ImportAuditLog  # noqa: E402, F401
