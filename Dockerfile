# ==============================================================================
# Multi-stage Production Dockerfile for Goddess AI / AI-Modrator
# Python 3.12-slim base with non-root security and dynamic PORT support
# ==============================================================================

# Build stage
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final runtime stage
FROM python:3.12-slim AS runner

WORKDIR /app

# Security: Create non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1001 appuser

# Copy installed dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV APP_ENV=production

# Copy application source
COPY --chown=appuser:appgroup app/ /app/app/
COPY --chown=appuser:appgroup alembic/ /app/alembic/
COPY --chown=appuser:appgroup alembic.ini /app/
COPY --chown=appuser:appgroup pyproject.toml /app/

# Switch to non-root user
USER appuser

# Expose default port
EXPOSE 8000

# Health check using python urllib
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://localhost:' + str(os.environ.get('PORT', 8000)) + '/health/live')" || exit 1

# Start command supporting Railway dynamic $PORT
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
