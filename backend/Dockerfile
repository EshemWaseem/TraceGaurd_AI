# Multi-stage production Dockerfile for TraceGuard AI Backend
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final minimal runtime container
FROM python:3.11-slim-bookworm AS runtime

# Create dedicated non-root user with UID 10001
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -s /bin/sh -M appuser

WORKDIR /app

# Copy python packages from builder
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy backend application source
COPY --chown=appuser:appuser alembic.ini .
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser app ./app

USER appuser

EXPOSE 8010

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, os; p = os.environ.get('PORT', '8010'); urllib.request.urlopen(f'http://127.0.0.1:{p}/api/health', timeout=3)" || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8010} --workers 2"]
