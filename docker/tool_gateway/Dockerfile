FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements-orchestrator.txt ./
RUN pip install --no-cache-dir -r requirements-orchestrator.txt

COPY src/ ./src/
COPY config/ ./config/

ENV PYTHONPATH=/app
ENV CAPABILITY_MANIFESTS_DIR=/app/config/capabilities/manifests
ENV REGISTRY_CONFIG_DIR=/app/config/registry
ENV TOOL_GATEWAY_AUDIT_DIR=/app/data/tool_gateway_audit

EXPOSE 8093

CMD ["python", "-m", "src.tool_gateway"]
