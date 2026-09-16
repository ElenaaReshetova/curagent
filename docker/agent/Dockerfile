FROM python:3.11-slim

WORKDIR /app

# Install Node.js for MCP Slack server
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY src/ ./src/
COPY skills/ ./skills/

# Copy and install MCP Slack (for agent-to-Slack via MCP)
COPY mcp-slack/ ./mcp-slack/
WORKDIR /app/mcp-slack
RUN npm ci 2>/dev/null || npm install
WORKDIR /app

# Clone and build MCP Jira (for agent-to-Jira via MCP)
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && git clone --depth 1 https://github.com/cosmix/jira-mcp.git /app/mcp-jira \
    && apt-get remove -y git && apt-get autoremove -y && apt-get clean && rm -rf /var/lib/apt/lists/*
WORKDIR /app/mcp-jira
RUN npm install && npm run build
WORKDIR /app

ENV PYTHONPATH=/app
ENV SKILLS_DIR=/app/skills

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.agent.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
