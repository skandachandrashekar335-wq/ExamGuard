import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.seat_assignment import SeatAssignment, SeatAssignmentStatus
from app.schemas.import_seat_assignments import (
    BulkCancelSeatItemResult,
    BulkSeatAssignmentItemResult,
)
from app.schemas.seat_assignment import SeatAssignmentCreate
from app.services import seat_assignment as seat_service

logger = logging.getLogger(__name__)


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
    results: list[BulkSeatAssignmentItemResult] = []
    assigned = 0
    skipped = 0
    failed = 0

    for item in items:
        try:
            result = _process_single_assignment(db, exam_hall_id, item)
            results.append(result)
            if result.status == "assigned":
                assigned += 1
            elif result.status == "skipped":
                skipped += 1
            else:
                failed += 1
        except Exception:
            logger.exception(
                "Unexpected error assigning seat for registration %d",
                item.exam_registration_id,
            )
            failed += 1
            results.append(
                BulkSeatAssignmentItemResult(
                    exam_registration_id=item.exam_registration_id,
                    seat_number=item.seat_number.strip() if item.seat_number else "",
                    status="failed",
                    error="Unexpected error",
                )
            )

    return {
        "total": len(items),
        "assigned": assigned,
        "skipped": skipped,
        "failed": failed,
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
    results: list[BulkCancelSeatItemResult] = []
    cancelled = 0
    skipped = 0
    failed = 0

    for aid in assignment_ids:
        try:
            result = _process_single_cancel(db, aid)
            results.append(result)
            if result.status == "cancelled":
                cancelled += 1
            elif result.status == "skipped":
                skipped += 1
            else:
                failed += 1
        except Exception:
            logger.exception("Unexpected error cancelling assignment %d", aid)
            failed += 1
            results.append(
                BulkCancelSeatItemResult(
                    assignment_id=aid,
                    status="failed",
                    error="Unexpected error",
                )
            )

    return {
        "total": len(assignment_ids),
        "cancelled": cancelled,
        "skipped": skipped,
        "failed": failed,
        "results": results,
    }
