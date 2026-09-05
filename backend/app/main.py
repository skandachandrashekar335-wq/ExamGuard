from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.database import engine
from app.services.monitoring.alert_buffer import AlertBuffer
from app.services.monitoring.connection_manager import ConnectionManager
from app.services.monitoring.event_buffer import EventBuffer
from app.services.monitoring.event_publisher import EventPublisher
from app.services.monitoring.publisher import init_monitoring_publisher

settings = get_settings()


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(v1_router, prefix=settings.API_V1_PREFIX)

    # Initialize monitoring publisher
    connection_manager = ConnectionManager(
        max_connections=settings.MONITORING_MAX_CONNECTIONS
    )
    event_buffer = EventBuffer(capacity=settings.MONITORING_EVENT_BUFFER_SIZE)
    alert_buffer = AlertBuffer(capacity=settings.MONITORING_ALERT_BUFFER_SIZE)
    publisher = EventPublisher(connection_manager, event_buffer, alert_buffer)
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

    return application


app = create_app()
