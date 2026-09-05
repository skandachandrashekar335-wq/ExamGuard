"""ERP adapter abstraction layer.

Provides a common interface for ERP system synchronization.
The adapter pattern allows switching between different ERP systems
without affecting the core application logic.

Architecture:
    ERP ADAPTER (this module)
        ↓
    ERP-SPECIFIC IMPLEMENTATIONS
    (e.g., SIS, SIS+Cloud, OnPremise)

Core contract:
- sync_students(): Sync student records from ERP
- sync_subjects(): Sync subject/exam records
- sync_exams(): Sync examination records
- sync_registrations(): Sync registration records
- sync_attendance(): Sync attendance records
- get_sync_status(): Get synchronization status/logs
- handle_sync_error(): Error handling and retry logic
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


class ErpSyncStatus:
    """Status of ERP synchronization operations."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ErpSyncLog:
    """Log entry for an ERP sync operation."""

    def __init__(
        self,
        operation: str,
        status: str,
        records_processed: int = 0,
        records_succeeded: int = 0,
        records_failed: int = 0,
        error_message: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ):
        self.operation = operation
        self.status = status
        self.records_processed = records_processed
        self.records_succeeded = records_succeeded
        self.records_failed = records_failed
        self.error_message = error_message
        self.started_at = started_at or datetime.now(timezone.utc)
        self.completed_at = completed_at


class ErpAdapter:
    """Abstract base class for ERP system adapters.

    Subclasses must implement the sync methods to connect to their
    specific ERP system. The adapter handles:
    - Authentication/credentials
    - API client construction
    - Response parsing
    - Error handling
    - Sync status logging
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.status: str = ErpSyncStatus.PENDING
        self.logs: list[ErpSyncLog] = []

    # ------------------------------------------------------------------
    # Core sync methods (must be implemented by subclasses)
    # ------------------------------------------------------------------

    def sync_students(self) -> dict[str, any]:
        """Synchronize student records from ERP system.

        Returns dict with {
            "total_in_erp": int,
            "new_added": int,
            "updated": int,
            "skipped": int,
            "errors": int,
        }
        """
        raise NotImplementedError("Subclasses must implement sync_students")

    def sync_subjects(self) -> dict[str, any]:
        """Synchronize subject/exam records from ERP system.

        Returns dict with {
            "total_in_erp": int,
            "new_added": int,
            "updated": int,
            "skipped": int,
            "errors": int,
        }
        """
        raise NotImplementedError("Subclasses must implement sync_subjects")

    def sync_exams(self) -> dict[str, any]:
        """Synchronize examination records from ERP system.

        Returns dict with {
            "total_in_erp": int,
            "new_added": int,
            "updated": int,
            "skipped": int,
            "errors": int,
        }
        """
        raise NotImplementedError("Subclasses must implement sync_exams")

    def sync_registrations(self) -> dict[str, any]:
        """Synchronize registration records from ERP system.

        Returns dict with {
            "total_in_erp": int,
            "new_added": int,
            "updated": int,
            "skipped": int,
            "errors": int,
        }
        """
        raise NotImplementedError("Subclasses must implement sync_registrations")

    def sync_attendance(self) -> dict[str, any]:
        """Synchronize attendance records from ERP system.

        Returns dict with {
            "total_in_erp": int,
            "new_added": int,
            "updated": int,
            "skipped": int,
            "errors": int,
        }
        """
        raise NotImplementedError("Subclasses must implement sync_attendance")

    # ------------------------------------------------------------------
    # Helper methods (optional, override if needed)
    # ------------------------------------------------------------------

    def get_sync_status(self) -> dict[str, any]:
        """Get overall synchronization status."""
        return {
            "status": self.status,
            "total_logs": len(self.logs),
            "last_operation": self.logs[-1].operation if self.logs else None,
            "last_result": self.logs[-1].status if self.logs else None,
        }

    def handle_sync_error(
        self,
        operation: str,
        error: Exception,
        records_processed: int,
    ) -> None:
        """Handle sync errors with logging and retry logic.

        Args:
            operation: The sync operation that failed.
            error: The exception that was raised.
            records_processed: How many records were processed before the error.
        """
        log = ErpSyncLog(
            operation=operation,
            status=ErpSyncStatus.FAILED,
            records_processed=records_processed,
            error_message=str(error),
        )
        self.logs.append(log)
        self.status = ErpSyncStatus.FAILED
        logger.warning(
            "ERP sync error - operation=%s error=%s records_processed=%d",
            operation, error, records_processed,
        )


# Module-level logger
import logging
logger = logging.getLogger(__name__)