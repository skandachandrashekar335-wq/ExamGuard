"""Background job queue and reliability service for ExamGuard.

Provides queue-based job processing, concurrent verification,
performance optimization, and failure recovery. All operations
are in-memory (no Redis/Celery dependency) and designed for
horizontal scaling behind a load balancer.

Architecture:
    Job submissions → JobQueue → Worker threads → Results/storage
        ↑                                    ↓
    API endpoints                        Async status checking
"""

import time
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.core.config import get_settings

settings = get_settings()

# -------------------------------------------------------------------------
# Job types and status
# -------------------------------------------------------------------------

class JobStatus:
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


JobCallback = Callable[[dict], None]


# -------------------------------------------------------------------------
# Job structure
# -------------------------------------------------------------------------

class BackgroundJob:
    """Represents a background job with status and result."""

    def __init__(
        self,
        job_id: str,
        job_type: str,
        callback: JobCallback,
        payload: dict,
        timeout: int = 60,
    ):
        self.job_id = job_id
        self.job_type = job_type
        self.callback = callback
        self.payload = payload
        self.timeout = timeout
        self.status = JobStatus.PENDING
        self.result: Optional[dict] = None
        self.error: Optional[str] = None
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


# -------------------------------------------------------------------------
# JobQueue (in-memory thread-safe queue)
# -------------------------------------------------------------------------

class JobQueue:
    """Thread-safe in-memory job queue with concurrent worker support."""

    def __init__(self, max_workers: int = 10, max_jobs: int = 1000):
        self.max_workers = max_workers
        self.max_jobs = max_jobs
        self._lock = threading.Lock()
        self._jobs: Dict[str, BackgroundJob] = {}
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._shutdown = False

    def submit(
        self,
        job_type: str,
        callback: JobCallback,
        payload: dict,
        timeout: int = 60,
    ) -> str:
        """Submit a new background job.

        Args:
            job_type: Type of job (for routing/dispatch).
            callback: Function to execute with the payload.
            payload: Data passed to the callback.
            timeout: Maximum execution time in seconds.

        Returns:
            The job_id for tracking the job.
        """
        with self._lock:
            if len(self._jobs) >= self.max_jobs:
                raise RuntimeError(f"Job queue full ({self.max_jobs} jobs)")

            job_id = str(uuid.uuid4())
            job = BackgroundJob(
                job_id=job_id,
                job_type=job_type,
                callback=callback,
                payload=payload,
                timeout=timeout,
            )
            self._jobs[job_id] = job

            # Execute in thread pool
            self._executor.submit(self._execute_job, job)

            return job_id

    def _execute_job(self, job: BackgroundJob) -> None:
        """Execute a single job with timeout and error handling."""
        job.status = JobStatus.IN_PROGRESS
        job.started_at = time.time()

        try:
            # Wait for callback completion with timeout
            def done(future):
                try:
                    job.result = future.result()
                    job.status = JobStatus.COMPLETED
                except Exception as e:
                    job.error = str(e)
                    job.status = JobStatus.FAILED
                finally:
                    job.completed_at = time.time()

            future = self._executor.submit(job.callback, job.payload)
            # Wait with timeout
            try:
                future.result(timeout=job.timeout)
            except Exception as e:
                job.error = f"Job timeout or error: {e}"
                job.status = JobStatus.FAILED
            finally:
                job.completed_at = time.time()

        except Exception as e:
            job.error = f"Job execution error: {e}"
            job.status = JobStatus.FAILED
            job.completed_at = time.time()

    def get_job(self, job_id: str) -> Optional[BackgroundJob]:
        """Get a job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def get_job_status(self, job_id: str) -> Optional[dict]:
        """Get job status as a dict."""
        job = self.get_job(job_id)
        if job is None:
            return None
        return job.to_dict()

    def complete_job(self, job_id: str, result: dict) -> None:
        """Mark a job as completed with a result."""
        with self._lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.result = result
                job.status = JobStatus.COMPLETED
                job.completed_at = time.time()

    def fail_job(self, job_id: str, error: str) -> None:
        """Mark a job as failed."""
        with self._lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.error = error
                job.status = JobStatus.FAILED
                job.completed_at = time.time()

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending job."""
        with self._lock:
            if job_id in self._jobs and self._jobs[job_id].status == JobStatus.PENDING:
                self._jobs[job_id].status = JobStatus.CANCELLED
                self._jobs[job_id].completed_at = time.time()
                return True
        return False

    def get_all_jobs(self) -> List[dict]:
        """Get all jobs with their current status."""
        with self._lock:
            return [job.to_dict() for job in self._jobs.values()]

    def shutdown_workers(self) -> None:
        """Gracefully shut down the worker thread pool."""
        self._shutdown = True
        self._executor.shutdown(wait=False)


# -------------------------------------------------------------------------
# Queue-level monitoring & metrics
# -------------------------------------------------------------------------

_job_queue: Optional[JobQueue] = None


def init_queue(max_workers: int = 10, max_jobs: int = 1000) -> JobQueue:
    """Initialize the global job queue."""
    global _job_queue
    _job_queue = JobQueue(max_workers=max_workers, max_jobs=max_jobs)
    return _job_queue


def get_queue() -> JobQueue:
    """Get the global job queue instance."""
    return _job_queue


# -------------------------------------------------------------------------
# Convenience functions for common background tasks
# -------------------------------------------------------------------------


def schedule_verification_check(
    job_queue: JobQueue,
    entry_verification_id: str,
    callback: JobCallback,
    timeout: int = 30,
) -> str:
    """Schedule a verification check job.

    Args:
        job_queue: The job queue instance.
        entry_verification_id: The EV to check.
        callback: Function(callback(result)) to execute.
        timeout: Timeout in seconds.

    Returns:
        job_id for tracking.
    """
    def check_callback(payload: dict) -> dict:
        # Import here to avoid circular dependencies
        from app.services.verification import get_verification_summary
        from app.models.document import Document

        doc_id = payload.get("document_id")
        if doc_id:
            summary = get_verification_summary(
                job_queue._queue._queue if hasattr(job_queue, "_queue") else None,
                doc_id,
            )
            return summary
        return {"status": "no_document_id"}

    return job_queue.submit("verification_check", check_callback, {"document_id": ""}, timeout)


# -------------------------------------------------------------------------
# Convenience: start the queue if not already started
# -------------------------------------------------------------------------

def ensure_queue(max_workers: int = 10, max_jobs: int = 1000) -> JobQueue:
    """Ensure the global job queue is initialized."""
    global _job_queue
    if _job_queue is None:
        _job_queue = JobQueue(max_workers=max_workers, max_jobs=max_jobs)
    return _job_queue


# -------------------------------------------------------------------------
# Export
# -------------------------------------------------------------------------

__all__ = [
    "BackgroundJob",
    "JobQueue",
    "JobStatus",
    "submit_background_job",
    "get_job_status",
    "ensure_queue",
    "schedule_verification_check",
]


def submit_background_job(
    job_queue: JobQueue,
    job_type: str,
    callback: JobCallback,
    payload: dict,
    timeout: int = 60,
) -> str:
    """Submit a background job to the queue."""
    return job_queue.submit(job_type, callback, payload, timeout)