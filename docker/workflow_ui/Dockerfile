FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements-orchestrator.txt ./
RUN pip install --no-cache-dir -r requirements-orchestrator.txt

COPY src/ ./src/
COPY skills/ ./skills/
COPY config/ ./config/

ENV PYTHONPATH=/app
ENV WORKFLOW_CONFIG_DIR=/app/config/workflows
ENV TEMPORAL_UI_URL=http://localhost:8088

EXPOSE 8092

CMD ["python", "-m", "src.workflow_ui"]
