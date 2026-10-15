# Dockerfile — AI Compliance Runtime (STUB).
# Finalized in Phase 10 (multi-stage, lockfile-only install, CPU-only).
# This stub documents the intended shape; it is not built in Phase 1.

FROM python:3.11-slim

WORKDIR /app

# Phase 10 will copy requirements.lock and install with --no-deps from the
# lockfile only (C-44), then copy src/ and configs/.
COPY pyproject.toml requirements.lock ./
# RUN pip install --no-cache-dir -r requirements.lock

COPY src/ ./src/
COPY configs/ ./configs/

# Placeholder entrypoint; the real HTTP server arrives in Phase 6.
CMD ["python", "-c", "print('compliance-runtime: Dockerfile stub (Phase 10)')"]
