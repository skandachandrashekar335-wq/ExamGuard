"""Production readiness and observability for ExamGuard.

Provides health checks, application logging configuration, metrics,
and deployment utilities. All functions are observational only —
no business logic mutations.

This phase wraps up the complete application with production-grade
observability and deployment readiness features.
"""

import logging
import sys
import time
import json
import threading
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.core.config import get_settings

settings = get_settings()


# -------------------------------------------------------------------------
# Logging configuration
# -------------------------------------------------------------------------

def setup_logging() -> logging.Logger:
    """Configure application logging with proper format and handlers.

    Logs include:
    - Timestamp (ISO format)
    - Logger name
    - Log level
    - Message
    - No sensitive data in format strings
    """
    logger = logging.getLogger("examguard")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # Avoid adding handlers if already configured
    if logger.handlers:
        return logger

    # Console handler with structured format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # Simple, safe format — no sensitive data
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


# -------------------------------------------------------------------------
# Health check endpoint utilities
# -------------------------------------------------------------------------


class HealthStatus:
    """Health check status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


def check_database() -> dict:
    """Check database connectivity and query execution via live SELECT 1."""
    import time
    from sqlalchemy import text
    from app.core.database import engine

    start_time = time.monotonic()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            alembic_rev = None
            try:
                rev_result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
                if rev_result:
                    alembic_rev = str(rev_result[0])
            except Exception:
                pass
        latency_ms = round((time.monotonic() - start_time) * 1000, 2)
        return {
            "status": HealthStatus.HEALTHY,
            "dialect": engine.dialect.name,
            "alembic_version": alembic_rev,
            "latency_ms": latency_ms,
            "details": f"Database connected ({engine.dialect.name})",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        latency_ms = round((time.monotonic() - start_time) * 1000, 2)
        return {
            "status": HealthStatus.UNHEALTHY,
            "dialect": getattr(engine, "dialect", None) and engine.dialect.name or "unknown",
            "alembic_version": None,
            "latency_ms": latency_ms,
            "details": f"Database connection error: {type(e).__name__}",
            "timestamp": datetime.now().isoformat(),
        }


def check_redis() -> dict:
    """Check Redis connectivity (placeholder — Redis not configured).

    Returns a dict with health status.
    """
    # Redis is not part of the ExamGuard infrastructure
    return {
        "status": HealthStatus.HEALTHY,
        "details": "Redis not configured (in-memory queue active)",
        "timestamp": datetime.now().isoformat(),
    }


def check_storage() -> dict:
    """Check storage backend connectivity and readiness."""
    from app.core.config import get_settings
    current_settings = get_settings()

    if current_settings.APP_ENV == "production" or current_settings.CLOUDINARY_CLOUD_NAME:
        has_creds = bool(
            current_settings.CLOUDINARY_CLOUD_NAME
            and current_settings.CLOUDINARY_API_KEY
            and current_settings.CLOUDINARY_API_SECRET
        )
        if not has_creds:
            return {
                "status": HealthStatus.UNHEALTHY if current_settings.APP_ENV == "production" else HealthStatus.DEGRADED,
                "backend": "cloudinary",
                "details": "Cloudinary credentials incomplete",
                "timestamp": datetime.now().isoformat(),
            }
        return {
            "status": HealthStatus.HEALTHY,
            "backend": "cloudinary",
            "cloud_name": current_settings.CLOUDINARY_CLOUD_NAME,
            "details": "Cloudinary configuration valid",
            "timestamp": datetime.now().isoformat(),
        }
    else:
        try:
            from app.storage.local import LocalStorage
            local = LocalStorage(base_dir=getattr(current_settings, "LOCAL_STORAGE_PATH", "./uploads"))
            key = local.generate_key("health_check.txt")
            assert key.startswith("documents/")
            return {
                "status": HealthStatus.HEALTHY,
                "backend": "local",
                "details": "Local storage backend active",
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "status": HealthStatus.DEGRADED,
                "backend": "local",
                "details": f"Storage check error: {type(e).__name__}",
                "timestamp": datetime.now().isoformat(),
            }


def check_face_verification() -> dict:
    """Check biometric face verification provider status and neural model availability."""
    from app.core.config import get_settings
    current_settings = get_settings()
    provider = current_settings.FACE_VERIFICATION_PROVIDER

    if current_settings.APP_ENV == "production" and provider == "deterministic":
        return {
            "status": HealthStatus.UNHEALTHY,
            "provider": provider,
            "details": "Deterministic face provider prohibited in production",
            "timestamp": datetime.now().isoformat(),
        }

    if provider == "uniface":
        try:
            import uniface  # noqa: F401
            from uniface.detection import RetinaFace  # noqa: F401
            from uniface.recognition import ArcFace  # noqa: F401
            return {
                "status": HealthStatus.HEALTHY,
                "provider": "uniface",
                "details": "UniFace models available (RetinaFace + ArcFace)",
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY if current_settings.APP_ENV == "production" else HealthStatus.DEGRADED,
                "provider": "uniface",
                "details": f"UniFace models unavailable: {type(e).__name__}",
                "timestamp": datetime.now().isoformat(),
            }

    return {
        "status": HealthStatus.HEALTHY,
        "provider": provider,
        "details": f"Face verification configured with provider '{provider}'",
        "timestamp": datetime.now().isoformat(),
    }


def check_ocr() -> dict:
    """Check Tesseract OCR executable availability."""
    import shutil
    import subprocess
    from app.core.config import get_settings
    current_settings = get_settings()

    tesseract_cmd = current_settings.TESSERACT_CMD or "tesseract"
    resolved_path = shutil.which(tesseract_cmd)

    if not resolved_path:
        return {
            "status": HealthStatus.DEGRADED if current_settings.APP_ENV != "production" else HealthStatus.UNHEALTHY,
            "binary": tesseract_cmd,
            "found": False,
            "details": f"Tesseract binary not found at '{tesseract_cmd}'",
            "timestamp": datetime.now().isoformat(),
        }

    try:
        proc = subprocess.run([resolved_path, "--version"], capture_output=True, text=True, timeout=2)
        version = proc.stdout.splitlines()[0] if proc.stdout else "available"
        return {
            "status": HealthStatus.HEALTHY,
            "binary": resolved_path,
            "found": True,
            "version": version,
            "details": "Tesseract OCR binary executable",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "status": HealthStatus.DEGRADED,
            "binary": resolved_path,
            "found": True,
            "details": f"Tesseract execution check error: {type(e).__name__}",
            "timestamp": datetime.now().isoformat(),
        }


def check_readiness() -> dict:
    """Aggregate readiness status for production readiness probes."""
    from app.core.config import get_settings
    current_settings = get_settings()

    db_check = check_database()
    storage_check = check_storage()
    monitoring_check = check_monitoring()
    face_check = check_face_verification()
    ocr_check = check_ocr()

    is_ready = (
        db_check["status"] == HealthStatus.HEALTHY
        and storage_check["status"] == HealthStatus.HEALTHY
        and face_check["status"] != HealthStatus.UNHEALTHY
        and ocr_check["status"] != HealthStatus.UNHEALTHY
    )

    return {
        "ready": is_ready,
        "app_env": current_settings.APP_ENV,
        "status": HealthStatus.HEALTHY if is_ready else HealthStatus.UNHEALTHY,
        "checks": {
            "database": db_check,
            "storage": storage_check,
            "monitoring": monitoring_check,
            "face_verification": face_check,
            "ocr": ocr_check,
        },
        "timestamp": datetime.now().isoformat(),
    }


def check_monitoring() -> dict:
    """Check monitoring system connectivity.

    Returns a dict with health status.
    """
    from app.services.queue.queue import get_queue

    try:
        queue = get_queue()
        # Just verify the queue is initialized
        status = "healthy"
        details = "Monitoring queue check passed"
    except Exception as e:
        status = "degraded"
        details = f"Monitoring check error: {type(e).__name__}"

    return {
        "status": status,
        "details": details,
        "timestamp": datetime.now().isoformat(),
    }


# -------------------------------------------------------------------------
# FastAPI health check endpoint setup
# -------------------------------------------------------------------------

def add_health_routes(app: FastAPI) -> None:
    """Add health check routes to the FastAPI application.

    Endpoints:
    - GET /health/status — Overall health status
    - GET /health/database — Database connectivity
    - GET /health/storage — Storage backend connectivity
    - GET /health/monitoring — Monitoring system status
    """

    @app.get("/health/status", include_in_schema=False)
    async def health_status() -> JSONResponse:
        """Overall application health status."""
        db_check = check_database()
        storage_check = check_storage()
        monitoring_check = check_monitoring()

        # Overall status: unhealthy if any component is unhealthy
        all_healthy = all(
            c["status"] == HealthStatus.HEALTHY for c in [db_check, storage_check, monitoring_check]
        )

        overall = HealthStatus.HEALTHY if all_healthy else HealthStatus.UNHEALTHY

        return JSONResponse(
            content={
                "status": overall,
                "checks": {
                    "database": db_check,
                    "storage": storage_check,
                    "monitoring": monitoring_check,
                },
                "timestamp": datetime.now().isoformat(),
            },
            status_code=200 if overall == HealthStatus.HEALTHY else 503,
        )

    @app.get("/health/database", include_in_schema=False)
    async def health_database() -> JSONResponse:
        """Database health check endpoint."""
        return JSONResponse(content=check_database(), status_code=200)

    @app.get("/health/storage", include_in_schema=False)
    async def health_storage() -> JSONResponse:
        """Storage backend health check endpoint."""
        return JSONResponse(content=check_storage(), status_code=200)

    @app.get("/health/monitoring", include_in_schema=False)
    async def health_monitoring() -> JSONResponse:
        """Monitoring system health check endpoint."""
        return JSONResponse(content=check_monitoring(), status_code=200)

    @app.get("/health/face-verification", include_in_schema=False)
    async def health_face_verification() -> JSONResponse:
        """Face verification provider status endpoint."""
        return JSONResponse(content=check_face_verification(), status_code=200)

    @app.get("/health/ocr", include_in_schema=False)
    async def health_ocr() -> JSONResponse:
        """OCR binary status endpoint."""
        return JSONResponse(content=check_ocr(), status_code=200)

    @app.get("/health/ready", include_in_schema=False)
    async def health_ready() -> JSONResponse:
        """Readiness probe endpoint for load balancers and orchestrators."""
        readiness = check_readiness()
        status_code = 200 if readiness["ready"] else 503
        return JSONResponse(content=readiness, status_code=status_code)


# -------------------------------------------------------------------------
# Metrics endpoint
# -------------------------------------------------------------------------

def add_metrics_routes(app: FastAPI) -> None:
    """Add metrics endpoints to the FastAPI application.

    Exposes basic application metrics for observability dashboards.
    """

    # Simple in-memory metrics (would be backed by Prometheus in production)
    metrics_data: Dict[str, Any] = {
        "requests_total": 0,
        "requests_by_path:": {},
        "requests_by_status:": {},
        "uptime_start": time.time(),
    }

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> JSONResponse:
        """Exposure of application metrics.

        Note: In production, would use Prometheus client library.
        """
        uptime = time.time() - metrics_data.get("uptime_start", 0)
        metrics_data["requests_total"] = metrics_data.get("requests_total", 0) + 1

        return JSONResponse(
            content={
                "uptime_seconds": uptime,
                "total_requests": metrics_data.get("requests_total", 0),
                " by_path": metrics_data.get("requests_by_path:", {}),
                "by_status": metrics_data.get("requests_by_status:", {}),
            },
            status_code=200,
        )


# -------------------------------------------------------------------------
# Production startup helper
# -------------------------------------------------------------------------

def run_production(app: FastAPI, host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the FastAPI application with production-ready settings.

    Includes:
    - Health check routes
    - Metrics routes
    - Proper logging configuration
    - Signal handling for graceful shutdown
    """
    # Setup logging
    logger = setup_logging()
    logger.info("Starting ExamGuard production server")

    # Add health and metrics routes
    add_health_routes(app)
    add_metrics_routes(app)

    import uvicorn

    # Signal handling for graceful shutdown
    shutdown_event = threading.Event()

    def signal_handler(signum, frame):
        logger.info("Received shutdown signal, initiating graceful shutdown...")
        shutdown_event.set()

    import signal
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    uvicorn.run(app, host=host, port=port)


# -------------------------------------------------------------------------
# Export
# -------------------------------------------------------------------------

__all__ = [
    "HealthStatus",
    "check_database",
    "check_redis",
    "check_storage",
    "check_monitoring",
    "add_health_routes",
    "add_metrics_routes",
    "run_production",
    "setup_logging",
]


# -------------------------------------------------------------------------
# When run as script, start the production server
# -------------------------------------------------------------------------

if __name__ == "__main__":
    from app.main import create_app

    app = create_app()
    run_production(app)