# ---------------------------------------------------------------------------
# ExamGuard Backend — Production Dockerfile
# ---------------------------------------------------------------------------
# Build:  docker build -t examguard-backend -f Dockerfile .
# Run:    docker run -p 8000:8000 --env-file .env examguard-backend
# ---------------------------------------------------------------------------

FROM python:3.11-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies:
#   - tesseract-ocr      : OCR engine
#   - poppler-utils      : PDF to image conversion (pdftoppm)
#   - libgl1 / libglib   : OpenCV headless runtime dependencies
#   - libpq-dev          : PostgreSQL client library (for psycopg2-binary)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Verify system binaries exist
RUN tesseract --version && pdftoppm -h

# ---------------------------------------------------------------------------
# Application stage
# ---------------------------------------------------------------------------
FROM base AS app

# Create non-root user
RUN groupadd -r examguard && useradd -r -g examguard -d /app -s /sbin/nologin examguard

WORKDIR /app

# Copy dependency definition first (for Docker layer caching)
COPY backend/pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir "." && \
    pip install --no-cache-dir "uniface[cpu]>=4.0.0" || true

# Copy application code
COPY backend/ ./

# Create upload directory and set ownership
RUN mkdir -p /app/uploads && chown -R examguard:examguard /app

# Switch to non-root user
USER examguard

# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------
EXPOSE 8000

# Health check — hits the /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run via uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
