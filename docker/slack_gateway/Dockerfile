FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements-slack_gateway.txt ./
RUN pip install --no-cache-dir -r requirements-slack_gateway.txt

COPY src/ ./src/

ENV PYTHONPATH=/app

EXPOSE 8090

CMD ["python", "-m", "uvicorn", "src.slack_gateway.main:app", "--host", "0.0.0.0", "--port", "8090"]
