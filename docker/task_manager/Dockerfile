FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements-orchestrator.txt ./
RUN pip install --no-cache-dir -r requirements-orchestrator.txt

COPY src/ ./src/
COPY skills/ ./skills/

ENV PYTHONPATH=/app

CMD ["python", "-m", "src.orchestrator", "starter"]
