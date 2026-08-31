from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.student import Student  # noqa: E402, F401
from app.models.document import Document  # noqa: E402, F401
