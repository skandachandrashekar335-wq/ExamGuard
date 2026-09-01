import logging
from datetime import date, time

from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus
from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.extraction import ExtractedField, ExtractionResult, ExtractionStatus
from app.models.hall_ticket_match import (
    HallTicketMatchResult,
    HallTicketMatchSignal,
    MatchSignalType,
    MatchStatus,
)
from app.models.seat_assignment import SeatAssignment, SeatAssignmentStatus
from app.models.student import Student
from app.models.subject import Subject
from app.services.student import normalize_usn

logger = logging.getLogger(__name__)


def _get_extracted_value(fields: list[ExtractedField], name: str) -> str | None:
    field = next((f for f in fields if f.field_name == name), None)
    if field:
        return field.corrected_value or field.extracted_value
    return None


def _create_signal(
    match_result_id: int,
    field_name: str,
    signal_type: str,
    extracted_value: str | None,
    expected_value: str | None,
    matched: bool,
    details: str | None = None,
) -> HallTicketMatchSignal:
    return HallTicketMatchSignal(
        match_result_id=match_result_id,
        field_name=field_name,
        extracted_value=extracted_value,
        expected_value=expected_value,
        matched=matched,
        signal_type=signal_type,
        details=details,
    )


def _match_student(
    db: Session,
    fields: list[ExtractedField],
    match_result_id: int,
) -> tuple[Student | None, list[HallTicketMatchSignal]]:
    signals = []
    usn_value = _get_extracted_value(fields, "usn")
    name_value = _get_extracted_value(fields, "name")

    if not usn_value:
        signals.append(_create_signal(
            match_result_id,
            "usn",
            MatchSignalType.STUDENT_USN.value,
            None,
            None,
            False,
            "USN not extracted from document",
        ))
        return None, signals

    normalized_usn = normalize_usn(usn_value)
    student = db.query(Student).filter(
        Student.usn == normalized_usn,
        Student.is_active == True,
    ).first()

    if not student:
        signals.append(_create_signal(
            match_result_id,
            "usn",
            MatchSignalType.STUDENT_USN.value,
            normalized_usn,
            None,
            False,
            f"No student found with USN '{normalized_usn}'",
        ))
        return None, signals

    signals.append(_create_signal(
        match_result_id,
        "usn",
        MatchSignalType.STUDENT_USN.value,
        normalized_usn,
        student.usn,
        True,
        f"Matched student: {student.name} (id={student.id})",
    ))

    if name_value:
        name_match = name_value.strip().lower() == student.name.strip().lower()
        signals.append(_create_signal(
            match_result_id,
            "name",
            MatchSignalType.STUDENT_NAME.value,
            name_value,
            student.name,
            name_match,
            "Name matches" if name_match else f"Name mismatch: expected '{student.name}'",
        ))
    else:
        signals.append(_create_signal(
            match_result_id,
            "name",
            MatchSignalType.STUDENT_NAME.value,
            None,
            student.name,
            False,
            "Name not extracted from document",
        ))

    return student, signals


def _match_exam(
    db: Session,
    fields: list[ExtractedField],
    match_result_id: int,
) -> tuple[Exam | None, list[HallTicketMatchSignal]]:
    signals = []
    exam_name_value = _get_extracted_value(fields, "exam_name")
    subject_value = _get_extracted_value(fields, "subject")
    exam_date_value = _get_extracted_value(fields, "exam_date")
    start_time_value = _get_extracted_value(fields, "start_time")

    query = db.query(Exam).filter(Exam.is_active == True)

    if exam_name_value:
        query = query.filter(Exam.exam_name.ilike(f"%{exam_name_value.strip()}%"))

    if subject_value:
        subject = db.query(Subject).filter(
            Subject.is_active == True,
            (Subject.name.ilike(f"%{subject_value.strip()}%"))
            | (Subject.code.ilike(f"%{subject_value.strip()}%")),
        ).first()
        if subject:
            query = query.filter(Exam.subject_id == subject.id)
            signals.append(_create_signal(
                match_result_id,
                "subject",
                MatchSignalType.SUBJECT.value,
                subject_value,
                f"{subject.code} - {subject.name}",
                True,
                f"Matched subject: {subject.code}",
            ))
        else:
            signals.append(_create_signal(
                match_result_id,
                "subject",
                MatchSignalType.SUBJECT.value,
                subject_value,
                None,
                False,
                f"No subject found matching '{subject_value}'",
            ))

    if exam_date_value:
        try:
            parsed_date = date.fromisoformat(exam_date_value)
            query = query.filter(Exam.exam_date == parsed_date)
            signals.append(_create_signal(
                match_result_id,
                "exam_date",
                MatchSignalType.EXAM_DATE.value,
                exam_date_value,
                exam_date_value,
                True,
                f"Filtering by exam date: {exam_date_value}",
            ))
        except ValueError:
            signals.append(_create_signal(
                match_result_id,
                "exam_date",
                MatchSignalType.EXAM_DATE.value,
                exam_date_value,
                None,
                False,
                f"Could not parse date: '{exam_date_value}'",
            ))

    if start_time_value:
        try:
            parsed_time = time.fromisoformat(start_time_value)
            query = query.filter(Exam.start_time == parsed_time)
            signals.append(_create_signal(
                match_result_id,
                "start_time",
                MatchSignalType.START_TIME.value,
                start_time_value,
                start_time_value,
                True,
                f"Filtering by start time: {start_time_value}",
            ))
        except ValueError:
            signals.append(_create_signal(
                match_result_id,
                "start_time",
                MatchSignalType.START_TIME.value,
                start_time_value,
                None,
                False,
                f"Could not parse time: '{start_time_value}'",
            ))

    exam = query.first()

    if exam_name_value:
        if exam:
            signals.append(_create_signal(
                match_result_id,
                "exam_name",
                MatchSignalType.EXAM_NAME.value,
                exam_name_value,
                exam.exam_name,
                True,
                f"Matched exam: {exam.exam_name} (id={exam.id})",
            ))
        else:
            signals.append(_create_signal(
                match_result_id,
                "exam_name",
                MatchSignalType.EXAM_NAME.value,
                exam_name_value,
                None,
                False,
                f"No exam found matching '{exam_name_value}'",
            ))
    else:
        signals.append(_create_signal(
            match_result_id,
            "exam_name",
            MatchSignalType.EXAM_NAME.value,
            None,
            None,
            False,
            "Exam name not extracted from document",
        ))

    return exam, signals


def _match_registration(
    db: Session,
    student: Student | None,
    exam: Exam | None,
    match_result_id: int,
) -> tuple[ExamRegistration | None, list[HallTicketMatchSignal]]:
    signals = []

    if not student or not exam:
        signals.append(_create_signal(
            match_result_id,
            "registration",
            MatchSignalType.REGISTRATION.value,
            None,
            None,
            False,
            "Cannot check registration: student or exam not identified",
        ))
        return None, signals

    registration = db.query(ExamRegistration).filter(
        ExamRegistration.student_id == student.id,
        ExamRegistration.exam_id == exam.id,
    ).first()

    if not registration:
        signals.append(_create_signal(
            match_result_id,
            "registration",
            MatchSignalType.REGISTRATION.value,
            f"student_id={student.id}, exam_id={exam.id}",
            None,
            False,
            f"Student {student.usn} is not registered for exam {exam.exam_name}",
        ))
        return None, signals

    if registration.status == RegistrationStatus.CANCELLED.value:
        signals.append(_create_signal(
            match_result_id,
            "registration",
            MatchSignalType.REGISTRATION.value,
            f"student_id={student.id}, exam_id={exam.id}",
            f"status={registration.status}",
            False,
            f"Registration is cancelled (id={registration.id})",
        ))
        return None, signals

    signals.append(_create_signal(
        match_result_id,
        "registration",
        MatchSignalType.REGISTRATION.value,
        f"student_id={student.id}, exam_id={exam.id}",
        f"status={registration.status}",
        True,
        f"Valid registration (id={registration.id}, status={registration.status})",
    ))

    return registration, signals


def _match_seat_and_hall(
    db: Session,
    registration: ExamRegistration | None,
    fields: list[ExtractedField],
    match_result_id: int,
) -> tuple[SeatAssignment | None, list[HallTicketMatchSignal]]:
    signals = []
    hall_value = _get_extracted_value(fields, "exam_hall")
    seat_value = _get_extracted_value(fields, "seat_number")

    if not registration:
        if hall_value:
            signals.append(_create_signal(
                match_result_id,
                "exam_hall",
                MatchSignalType.EXAM_HALL.value,
                hall_value,
                None,
                False,
                "Cannot verify hall: no valid registration",
            ))
        if seat_value:
            signals.append(_create_signal(
                match_result_id,
                "seat_number",
                MatchSignalType.SEAT_NUMBER.value,
                seat_value,
                None,
                False,
                "Cannot verify seat: no valid registration",
            ))
        return None, signals

    assignment = db.query(SeatAssignment).filter(
        SeatAssignment.exam_registration_id == registration.id,
        SeatAssignment.status == SeatAssignmentStatus.ASSIGNED.value,
    ).first()

    if not assignment:
        if hall_value:
            signals.append(_create_signal(
                match_result_id,
                "exam_hall",
                MatchSignalType.EXAM_HALL.value,
                hall_value,
                None,
                False,
                "No seat assignment found for this registration",
            ))
        if seat_value:
            signals.append(_create_signal(
                match_result_id,
                "seat_number",
                MatchSignalType.SEAT_NUMBER.value,
                seat_value,
                None,
                False,
                "No seat assignment found for this registration",
            ))
        return None, signals

    hall = db.query(ExamHall).filter(ExamHall.id == assignment.exam_hall_id).first()

    if hall_value and hall:
        hall_match = (
            hall_value.strip().lower() in f"{hall.building} {hall.room_number}".lower()
            or f"{hall.building} {hall.room_number}".lower() in hall_value.strip().lower()
            or hall_value.strip().lower() == hall.building.lower()
            or hall_value.strip().lower() == hall.room_number.lower()
        )
        signals.append(_create_signal(
            match_result_id,
            "exam_hall",
            MatchSignalType.EXAM_HALL.value,
            hall_value,
            f"{hall.building} {hall.room_number}",
            hall_match,
            f"Matched hall: {hall.building} {hall.room_number}" if hall_match
            else f"Hall mismatch: expected '{hall.building} {hall.room_number}'",
        ))
    elif hall_value and not hall:
        signals.append(_create_signal(
            match_result_id,
            "exam_hall",
            MatchSignalType.EXAM_HALL.value,
            hall_value,
            None,
            False,
            "Could not resolve assigned hall",
        ))
    elif not hall_value:
        signals.append(_create_signal(
            match_result_id,
            "exam_hall",
            MatchSignalType.EXAM_HALL.value,
            None,
            f"{hall.building} {hall.room_number}" if hall else None,
            False,
            "Hall not extracted from document",
        ))

    if seat_value:
        seat_match = seat_value.strip().upper() == assignment.seat_number.strip().upper()
        signals.append(_create_signal(
            match_result_id,
            "seat_number",
            MatchSignalType.SEAT_NUMBER.value,
            seat_value,
            assignment.seat_number,
            seat_match,
            f"Matched seat: {assignment.seat_number}" if seat_match
            else f"Seat mismatch: expected '{assignment.seat_number}'",
        ))
    else:
        signals.append(_create_signal(
            match_result_id,
            "seat_number",
            MatchSignalType.SEAT_NUMBER.value,
            None,
            assignment.seat_number,
            False,
            "Seat number not extracted from document",
        ))

    return assignment, signals


def _determine_overall_status(
    signals: list[HallTicketMatchSignal],
) -> str:
    if not signals:
        return MatchStatus.NOT_FOUND.value

    matched_count = sum(1 for s in signals if s.matched)
    total_count = len(signals)

    critical_fields = {"student_usn", "registration"}
    critical_matched = any(
        s.matched for s in signals if s.signal_type in critical_fields
    )
    critical_present = any(
        s.signal_type in critical_fields for s in signals
    )

    if matched_count == total_count:
        return MatchStatus.MATCHED.value

    if critical_present and not critical_matched:
        return MatchStatus.NOT_FOUND.value

    if matched_count > 0:
        return MatchStatus.PARTIAL_MATCH.value

    return MatchStatus.MISMATCH.value


def match_hall_ticket(
    db: Session,
    document_id: int,
) -> HallTicketMatchResult:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise LookupError(f"Document {document_id} not found")

    extraction_result = (
        db.query(ExtractionResult)
        .filter(ExtractionResult.document_id == document_id)
        .order_by(ExtractionResult.id.desc())
        .first()
    )
    if not extraction_result:
        raise LookupError(f"No extraction results found for document {document_id}")

    if extraction_result.status not in (
        ExtractionStatus.COMPLETED.value,
        ExtractionStatus.REVIEW_REQUIRED.value,
    ):
        raise ValueError(
            f"Document {document_id} extraction is not completed "
            f"(status: {extraction_result.status})"
        )

    fields = (
        db.query(ExtractedField)
        .filter(ExtractedField.extraction_result_id == extraction_result.id)
        .order_by(ExtractedField.id)
        .all()
    )

    match_result = HallTicketMatchResult(
        document_id=document_id,
        extraction_result_id=extraction_result.id,
        overall_status=MatchStatus.NOT_FOUND.value,
    )
    db.add(match_result)
    db.flush()

    all_signals = []

    student, student_signals = _match_student(db, fields, match_result.id)
    all_signals.extend(student_signals)

    exam, exam_signals = _match_exam(db, fields, match_result.id)
    all_signals.extend(exam_signals)

    registration, reg_signals = _match_registration(db, student, exam, match_result.id)
    all_signals.extend(reg_signals)

    assignment, seat_signals = _match_seat_and_hall(
        db, registration, fields, match_result.id
    )
    all_signals.extend(seat_signals)

    for signal in all_signals:
        db.add(signal)

    overall_status = _determine_overall_status(all_signals)
    match_result.overall_status = overall_status

    if student:
        match_result.student_id = student.id
    if exam:
        match_result.exam_id = exam.id
    if registration:
        match_result.registration_id = registration.id
    if assignment:
        match_result.seat_assignment_id = assignment.id

    db.commit()
    db.refresh(match_result)
    return match_result


def get_latest_match_result(
    db: Session,
    document_id: int,
) -> HallTicketMatchResult | None:
    return (
        db.query(HallTicketMatchResult)
        .filter(HallTicketMatchResult.document_id == document_id)
        .order_by(HallTicketMatchResult.id.desc())
        .first()
    )
