# AgentBreaker Backend — Production Dockerfile
# Multi-stage build with non-root user and health check

# ── Stage 1: Install dependencies ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Production image ─────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install curl for health checks and tini for PID 1 signal handling
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Remove dev/test files from production image
RUN rm -rf tests/ .pytest_cache/ *.db *.db-shm *.db-wal .env* __pycache__/

# Set ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Cloud Run uses PORT env var (default 8080)
ENV PORT=8080
EXPOSE ${PORT}

# Health check — Cloud Run also uses this endpoint for liveness probes
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Use tini as PID 1 for proper signal handling (SIGTERM from Cloud Run)
ENTRYPOINT ["tini", "--"]

# Run uvicorn with production settings
# - workers=1 because Cloud Run scales horizontally via instances
# - timeout-graceful-shutdown=25 to handle Cloud Run's 30s SIGTERM window
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --timeout-graceful-shutdown 25 --access-log"]
