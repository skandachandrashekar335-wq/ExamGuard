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


MAX_ERROR_SUMMARY_LENGTH = 2000
MAX_ERROR_SAMPLES = 10


def build_error_summary(results: Sequence[Any]) -> str | None:
    """Build a bounded error summary string from per-row results.

    Collects the first few error messages, truncated to
    ``MAX_ERROR_SUMMARY_LENGTH`` characters total.
    Returns None if no errors are present.
    """
    errors = [r.error for r in results if hasattr(r, "error") and r.error]
    if not errors:
        return None
    samples = errors[:MAX_ERROR_SAMPLES]
    suffix = f"\n... and {len(errors) - MAX_ERROR_SAMPLES} more errors" if len(errors) > MAX_ERROR_SAMPLES else ""
    text = "; ".join(samples) + suffix
    return text[:MAX_ERROR_SUMMARY_LENGTH] if len(text) > MAX_ERROR_SUMMARY_LENGTH else text
