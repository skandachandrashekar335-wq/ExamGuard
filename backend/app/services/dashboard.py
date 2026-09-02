import logging

from sqlalchemy.orm import Session

from app.models.exam import Exam
from app.models.exam_hall import ExamHall
from app.models.exam_registration import ExamRegistration, RegistrationStatus
from app.models.seat_assignment import SeatAssignment, SeatAssignmentStatus
from app.models.student import Student
from app.models.verification import VerificationDecision, VerificationOutcome

logger = logging.getLogger(__name__)


def _student_verification_status(
    registration: ExamRegistration,
    seat_assignment: SeatAssignment | None,
    latest_outcome: VerificationOutcome | None,
) -> dict:
    status = "NOT_UPLOADED"
    document_id = None
    extraction_check = None
    match_check = None
    review_check = None
    decision = None
    ocr_avg_confidence = None
    match_status = None
    verification_created_at = None

    if latest_outcome is not None:
        decision = latest_outcome.decision
        extraction_check = latest_outcome.extraction_check
        match_check = latest_outcome.match_check
        review_check = latest_outcome.review_check
        ocr_avg_confidence = latest_outcome.ocr_avg_confidence
        match_status = latest_outcome.match_status
        document_id = latest_outcome.document_id
        verification_created_at = (
            str(latest_outcome.created_at) if latest_outcome.created_at else None
        )

        if decision == VerificationDecision.VERIFIED.value:
            status = "VERIFIED"
        elif decision == VerificationDecision.FAILED.value:
            status = "FAILED"
        elif decision == VerificationDecision.REVIEW_REQUIRED.value:
            status = "REVIEW_REQUIRED"
        elif decision == VerificationDecision.INCOMPLETE.value:
            status = "INCOMPLETE"

    return {
        "student_id": registration.student.id,
        "student_usn": registration.student.usn,
        "student_name": registration.student.name,
        "registration_id": registration.id,
        "registration_status": registration.status,
        "seat_assignment_id": seat_assignment.id if seat_assignment else None,
        "seat_number": seat_assignment.seat_number if seat_assignment else None,
        "hall_name": (
            f"{seat_assignment.hall.building} {seat_assignment.hall.room_number}"
            if seat_assignment and seat_assignment.hall
            else None
        ),
        "verification_status": status,
        "document_id": document_id,
        "extraction_check": extraction_check,
        "match_check": match_check,
        "review_check": review_check,
        "decision": decision,
        "ocr_avg_confidence": ocr_avg_confidence,
        "match_status": match_status,
        "verification_created_at": verification_created_at,
    }


def get_exam_dashboard(db: Session, exam_id: int) -> dict:
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise LookupError(f"Exam {exam_id} not found")

    registrations = (
        db.query(ExamRegistration)
        .filter(
            ExamRegistration.exam_id == exam_id,
            ExamRegistration.status == RegistrationStatus.REGISTERED.value,
        )
        .all()
    )

    seat_map: dict[int, SeatAssignment] = {}
    seats = (
        db.query(SeatAssignment)
        .filter(
            SeatAssignment.exam_id == exam_id,
            SeatAssignment.status == SeatAssignmentStatus.ASSIGNED.value,
        )
        .all()
    )
    for s in seats:
        seat_map[s.exam_registration_id] = s

    outcome_map: dict[tuple[int, int], VerificationOutcome] = {}
    if registrations:
        student_exam_pairs = [(r.student_id, r.exam_id) for r in registrations]
        outcomes = (
            db.query(VerificationOutcome)
            .filter(
                VerificationOutcome.exam_id == exam_id,
                VerificationOutcome.student_id.isnot(None),
            )
            .all()
        )
        for o in outcomes:
            key = (o.student_id, o.exam_id)
            if key not in outcome_map or o.id > outcome_map[key].id:
                outcome_map[key] = o

    students = []
    total_verified = 0
    total_failed = 0
    total_review_required = 0
    total_incomplete = 0
    total_not_uploaded = 0
    total_seated = 0

    for reg in registrations:
        sa = seat_map.get(reg.id)
        if sa:
            total_seated += 1

        latest_outcome = outcome_map.get((reg.student_id, reg.exam_id))
        entry = _student_verification_status(reg, sa, latest_outcome)
        students.append(entry)

        vs = entry["verification_status"]
        if vs == "VERIFIED":
            total_verified += 1
        elif vs == "FAILED":
            total_failed += 1
        elif vs == "REVIEW_REQUIRED":
            total_review_required += 1
        elif vs == "INCOMPLETE":
            total_incomplete += 1
        else:
            total_not_uploaded += 1

    total_registered = len(registrations)
    verification_rate = (
        round(total_verified / total_registered * 100, 1)
        if total_registered > 0
        else 0.0
    )

    return {
        "summary": {
            "exam_id": exam.id,
            "exam_name": exam.exam_name,
            "exam_date": str(exam.exam_date),
            "total_registered": total_registered,
            "total_verified": total_verified,
            "total_failed": total_failed,
            "total_review_required": total_review_required,
            "total_incomplete": total_incomplete,
            "total_not_uploaded": total_not_uploaded,
            "total_seated": total_seated,
            "verification_rate": verification_rate,
        },
        "students": students,
    }
