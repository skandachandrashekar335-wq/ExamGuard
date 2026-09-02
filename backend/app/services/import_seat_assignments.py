from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.seat_assignment import SeatAssignment, SeatAssignmentStatus
from app.schemas.import_seat_assignments import (
    BulkCancelSeatItemResult,
    BulkSeatAssignmentItemResult,
)
from app.schemas.seat_assignment import SeatAssignmentCreate
from app.services import seat_assignment as seat_service
from app.services.import_common import count_import_results, process_import_items


def _process_single_assignment(
    db: Session, exam_hall_id: int, item
) -> BulkSeatAssignmentItemResult:
    seat_number = item.seat_number.strip()

    try:
        data = SeatAssignmentCreate(
            exam_registration_id=item.exam_registration_id,
            exam_hall_id=exam_hall_id,
            seat_number=seat_number,
            row_number=item.row_number,
            column_number=item.column_number,
        )
        assignment = seat_service.create_assignment(db, data)
        return BulkSeatAssignmentItemResult(
            exam_registration_id=item.exam_registration_id,
            seat_number=seat_number,
            status="assigned",
            assignment_id=assignment.id,
        )
    except LookupError as e:
        return BulkSeatAssignmentItemResult(
            exam_registration_id=item.exam_registration_id,
            seat_number=seat_number,
            status="failed",
            error=str(e),
        )
    except ValueError as e:
        return BulkSeatAssignmentItemResult(
            exam_registration_id=item.exam_registration_id,
            seat_number=seat_number,
            status="failed",
            error=str(e),
        )


def bulk_assign_seats(
    db: Session, exam_hall_id: int, items
) -> dict:
    def _process(item) -> BulkSeatAssignmentItemResult:
        return _process_single_assignment(db, exam_hall_id, item)

    def _error(item) -> BulkSeatAssignmentItemResult:
        return BulkSeatAssignmentItemResult(
            exam_registration_id=item.exam_registration_id,
            seat_number=item.seat_number.strip() if item.seat_number else "",
            status="failed",
            error="Unexpected error",
        )

    results = process_import_items(items, _process, _error)
    counts = count_import_results(results)

    return {
        "total": len(items),
        "assigned": counts.get("assigned", 0),
        "skipped": counts.get("skipped", 0),
        "failed": counts.get("failed", 0),
        "results": results,
    }


def _process_single_cancel(
    db: Session, assignment_id: int
) -> BulkCancelSeatItemResult:
    assignment = db.query(SeatAssignment).filter(
        SeatAssignment.id == assignment_id
    ).first()
    if not assignment:
        return BulkCancelSeatItemResult(
            assignment_id=assignment_id,
            status="failed",
            error=f"Assignment with id {assignment_id} not found",
        )

    if assignment.status == SeatAssignmentStatus.CANCELLED.value:
        return BulkCancelSeatItemResult(
            assignment_id=assignment_id,
            status="skipped",
            error=f"Assignment {assignment_id} is already cancelled",
        )

    assignment.status = SeatAssignmentStatus.CANCELLED.value

    try:
        db.commit()
        db.refresh(assignment)
    except IntegrityError:
        db.rollback()
        return BulkCancelSeatItemResult(
            assignment_id=assignment_id,
            status="failed",
            error="Failed to cancel assignment",
        )

    return BulkCancelSeatItemResult(
        assignment_id=assignment_id,
        status="cancelled",
    )


def bulk_cancel_assignments(
    db: Session, assignment_ids: list[int]
) -> dict:
    def _process(assignment_id: int) -> BulkCancelSeatItemResult:
        return _process_single_cancel(db, assignment_id)

    def _error(assignment_id: int) -> BulkCancelSeatItemResult:
        return BulkCancelSeatItemResult(
            assignment_id=assignment_id,
            status="failed",
            error="Unexpected error",
        )

    results = process_import_items(assignment_ids, _process, _error)
    counts = count_import_results(results)

    return {
        "total": len(assignment_ids),
        "cancelled": counts.get("cancelled", 0),
        "skipped": counts.get("skipped", 0),
        "failed": counts.get("failed", 0),
        "results": results,
    }
