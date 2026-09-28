ARG NODE_IMAGE=node:24-alpine
ARG PYTHON_IMAGE=python:3.13-slim

FROM ${NODE_IMAGE} AS frontend-builder
USER root
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM ${PYTHON_IMAGE} AS runtime
USER root
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SERVICEPILOT_PROJECT_DIR=/app \
    SERVICEPILOT_DB_PATH=/app/runtime/servicepilot.db \
    SERVICEPILOT_CHECKPOINT_PATH=/app/runtime/checkpoints.db \
    SERVICEPILOT_CHECKPOINT_MODE=sqlite \
    SERVICEPILOT_MODEL_MODE=mock \
    SERVICEPILOT_HOST=0.0.0.0 \
    SERVICEPILOT_PORT=8000

WORKDIR /app
COPY pyproject.toml README.md LICENSE THIRD_PARTY_NOTICES.md ./
COPY src/ ./src/
COPY config/ ./config/
COPY data/policies/ ./data/policies/
COPY evals/ ./evals/
COPY --from=frontend-builder /frontend/dist ./frontend/dist

RUN python -m pip install . && \
    useradd --create-home --uid 10001 servicepilot && \
    mkdir -p /app/runtime /app/reports && \
    chown -R servicepilot:servicepilot /app/runtime /app/reports

USER servicepilot
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)" || exit 1

CMD ["uvicorn", "servicepilot.api:app", "--host", "0.0.0.0", "--port", "8000"]
