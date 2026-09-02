import logging
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")

IMPORT_LIMITS: dict[str, int] = {
    "students": 500,
    "subjects": 200,
    "exams": 500,
    "registrations": 500,
    "registration_cancellations": 500,
    "seat_assignments": 200,
    "seat_assignment_cancellations": 200,
}


def process_import_items(
    items: Sequence[T],
    process_fn: Callable[[T], R],
    error_fn: Callable[[T], R],
) -> list[R]:
    """Process a list of import items, handling exceptions per item.

    For each item, calls process_fn. If it raises any exception,
    logs the error and appends the result of error_fn instead.
    Returns the full list of results.
    """
    results: list[R] = []
    for item in items:
        try:
            results.append(process_fn(item))
        except Exception:
            logger.exception("Unexpected error processing import item")
            results.append(error_fn(item))
    return results


def count_import_results(results: Sequence[Any]) -> dict[str, int]:
    """Count import results by their ``status`` field.

    Returns a dict mapping each status value to its count.
    """
    counts: dict[str, int] = {}
    for result in results:
        status = result.status
        counts[status] = counts.get(status, 0) + 1
    return counts
