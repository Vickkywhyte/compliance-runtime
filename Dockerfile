# Dockerfile — AI Compliance Runtime (Phase 10, finalized).
#
# Multi-stage build. The runtime has NO ML/LLM dependencies (ADR-013), so
# there is deliberately no torch / CUDA / huggingface install — the image is
# pure-Python and small. Deps are installed from the pinned lockfile (C-41,
# C-44); the project is installed non-editable so no /build .pth leaks into
# the runtime stage. Runs as a non-root user; secrets are kept out via
# .dockerignore (C-16, C-39).

# --- Stage 1: builder ----------------------------------------------------
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY pyproject.toml requirements.lock ./
COPY src/ ./src/

# Lockfile-only dependency install, then the project itself (non-editable).
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.lock \
 && pip install --no-cache-dir --no-deps .

# --- Stage 2: runtime ----------------------------------------------------
FROM python:3.11-slim AS runtime

# Copy the installed environment (site-packages + console scripts) from the
# builder. No apt packages are needed at runtime: the wheels (cryptography,
# numpy, pyarrow, reportlab, ...) are self-contained.
COPY --from=builder /usr/local/lib/python3.11/site-packages \
                    /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

WORKDIR /app
COPY src/              ./src/
COPY configs/          ./configs/
COPY scripts/          ./scripts/
COPY data/demo/        ./data/demo/
COPY pyproject.toml    ./
COPY requirements.lock ./

# Non-root user owning the writable runtime dirs.
RUN useradd --create-home --uid 1000 agent \
 && mkdir -p /app/data /app/logs /app/results \
 && chown -R agent:agent /app
USER agent

EXPOSE 8000 8501

# Default command: the Streamlit dashboard. Override CMD to run the FastAPI
# server:  uvicorn compliance_runtime.interception.server:app --host 0.0.0.0
CMD ["streamlit", "run", "src/compliance_runtime/dashboard/app.py", \
     "--server.port", "8501", "--server.address", "0.0.0.0"]
