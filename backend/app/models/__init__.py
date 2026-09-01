from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.student import Student  # noqa: E402, F401
from app.models.document import Document  # noqa: E402, F401
from app.models.extraction import ExtractionResult, ExtractedField  # noqa: E402, F401
from app.models.subject import Subject  # noqa: E402, F401
from app.models.exam import Exam  # noqa: E402, F401
