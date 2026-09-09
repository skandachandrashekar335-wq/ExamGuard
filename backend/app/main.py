import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import router as v1_router
from app.api.v1.auth import router as auth_router
from app.core.config import get_settings
from app.core.database import engine
from app.monitoring.production import add_health_routes, add_metrics_routes
from app.security.hardening import rate_limit_handler
from app.services.monitoring.alert_buffer import AlertBuffer
from app.services.monitoring.connection_manager import ConnectionManager
from app.services.monitoring.event_buffer import EventBuffer
from app.services.monitoring.event_publisher import EventPublisher
from app.services.monitoring.publisher import init_monitoring_publisher
from app.services.security_event_bridge import make_security_event_hook

settings = get_settings()


def _validate_production_config() -> None:
    """Log warnings for missing production configuration. Non-fatal."""
    if settings.APP_ENV == "development":
        return

    logger = logging.getLogger("examguard.startup")
    warnings = []

    if not settings.FIREBASE_PROJECT_ID:
        warnings.append("FIREBASE_PROJECT_ID not set — Firebase auth will fail")

    if settings.SECRET_KEY == "change-me-to-a-random-secret-key":
        warnings.append("SECRET_KEY is placeholder — reject in production")

    if settings.FACE_VERIFICATION_PROVIDER not in ("deterministic", "none", "uniface"):
        warnings.append(
            f"FACE_VERIFICATION_PROVIDER={settings.FACE_VERIFICATION_PROVIDER!r} "
            f"— expected 'deterministic', 'none', or 'uniface'"
        )

    if not settings.DATABASE_URL or "password" in settings.DATABASE_URL:
        warnings.append("DATABASE_URL may contain default credentials")

    for w in warnings:
        logger.warning("STARTUP: %s", w)


def create_app() -> FastAPI:
    _validate_production_config()

    application = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    # Rate limiting middleware (disabled under pytest to avoid shared-state conflicts)
    import sys
    is_test = "pytest" in sys.modules or settings.APP_ENV == "test"
    if not is_test:
        @application.middleware("http")
        async def _rate_limit(request, call_next):
            return await rate_limit_handler(request, call_next)

    application.include_router(auth_router, prefix=settings.API_V1_PREFIX)
    application.include_router(v1_router, prefix=settings.API_V1_PREFIX)

    # Initialize monitoring publisher
    connection_manager = ConnectionManager(
        max_connections=settings.MONITORING_MAX_CONNECTIONS
    )
    event_buffer = EventBuffer(capacity=settings.MONITORING_EVENT_BUFFER_SIZE)
    alert_buffer = AlertBuffer(capacity=settings.MONITORING_ALERT_BUFFER_SIZE)
    security_hook = make_security_event_hook()
    publisher = EventPublisher(
        connection_manager, event_buffer, alert_buffer,
        post_publish=security_hook,
    )
    init_monitoring_publisher(publisher)

    @application.get("/health")
    def health_check() -> dict[str, str | dict[str, str]]:
        result: dict[str, str | dict[str, str]] = {"status": "healthy"}
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            result["database"] = "connected"
        except Exception:
            result["database"] = "disconnected"
            result["status"] = "degraded"
        return result

    # Extended health/metrics endpoints (always registered)
    add_health_routes(application)
    add_metrics_routes(application)

    return application


app = create_app()