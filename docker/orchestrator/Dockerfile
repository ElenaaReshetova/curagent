FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements-orchestrator.txt ./
RUN pip install --no-cache-dir -r requirements-orchestrator.txt

COPY src/ ./src/
COPY skills/ ./skills/
COPY config/ ./config/

ENV PYTHONPATH=/app
ENV SKILLS_DIR=/app/skills
ENV WORKFLOW_CONFIG_DIR=/app/config/workflows

# Default: Temporal worker. Override CMD for kafka starter.
CMD ["python", "-m", "src.orchestrator", "worker"]
