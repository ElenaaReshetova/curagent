FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements-jira_gateway.txt ./
RUN pip install --no-cache-dir -r requirements-jira_gateway.txt

COPY src/ ./src/

ENV PYTHONPATH=/app

EXPOSE 8091

CMD ["python", "-m", "uvicorn", "src.jira_gateway.main:app", "--host", "0.0.0.0", "--port", "8091"]
