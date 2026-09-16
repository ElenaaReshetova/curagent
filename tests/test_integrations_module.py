"""Integrations module — MCP / A2A / ACP protocol connections."""

from fastapi.testclient import TestClient

from src.workflow_ui.main import app


def test_integrations_catalog_protocol_connections(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATFORM_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("MCP_CONFIG_DIR", str(tmp_path / "mcp"))
    (tmp_path / "mcp").mkdir(parents=True)
    (tmp_path / "mcp" / "servers.json").write_text(
        '''{
          "version": 1,
          "servers": [
            {
              "id": "filesystem",
              "name": "Filesystem",
              "description": "Local FS",
              "enabled": true,
              "type": "stdio",
              "command": "npx",
              "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
              "env": {},
              "tools": ["read_file"]
            }
          ]
        }
        ''',
        encoding="utf-8",
    )
    # Point A2A/ACP configs into tmp via monkeypatch of paths
    from src.platform.integrations import service as svc

    a2a = tmp_path / "a2a.json"
    acp = tmp_path / "acp.json"
    a2a.write_text('{"servers": {"research-agent": "http://localhost:9100"}}\n', encoding="utf-8")
    acp.write_text(
        '{"agent_servers": {"coder": {"command": "uv", "args": ["run", "agent"]}}}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "a2a_config_path", lambda: a2a)
    monkeypatch.setattr(svc, "acp_config_path", lambda: acp)

    client = TestClient(app)
    response = client.get("/api/v1/integrations")
    assert response.status_code == 200
    payload = response.json()
    assert "connections" in payload
    assert payload["metrics"]["total"] >= 3
    protocols = {c["protocol"] for c in payload["connections"]}
    assert protocols >= {"MCP", "A2A", "ACP"}
    assert "mcpServers" in payload["config"]
    assert "filesystem" in payload["config"]["mcpServers"]
    assert payload["config"]["mcpServers"]["filesystem"]["command"] == "npx"

    mcp_only = client.get("/api/v1/integrations", params={"protocol": "MCP"})
    assert mcp_only.status_code == 200
    assert all(c["protocol"] == "MCP" for c in mcp_only.json()["connections"])


def test_integrations_config_json_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_CONFIG_DIR", str(tmp_path / "mcp"))
    (tmp_path / "mcp").mkdir(parents=True)
    (tmp_path / "mcp" / "servers.json").write_text(
        '{"version": 1, "servers": []}\n', encoding="utf-8",
    )
    from src.platform.integrations import service as svc

    a2a = tmp_path / "a2a.json"
    acp = tmp_path / "acp.json"
    a2a.write_text('{"servers": {}}\n', encoding="utf-8")
    acp.write_text('{"agent_servers": {}}\n', encoding="utf-8")
    monkeypatch.setattr(svc, "a2a_config_path", lambda: a2a)
    monkeypatch.setattr(svc, "acp_config_path", lambda: acp)

    client = TestClient(app)
    document = {
        "mcpServers": {
            "memory": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-memory"],
                "env": {"DEBUG": "1"},
            }
        },
        "servers": {"local": "http://127.0.0.1:8000"},
        "agent_servers": {
            "goose": {"command": "goose", "args": ["acp"]},
        },
    }
    saved = client.put("/api/v1/integrations/config", json={"document": document})
    assert saved.status_code == 200
    body = saved.json()["document"]
    assert body["mcpServers"]["memory"]["command"] == "npx"
    assert body["servers"]["local"] == "http://127.0.0.1:8000"
    assert body["agent_servers"]["goose"]["command"] == "goose"

    detail = client.get("/api/v1/integrations/mcp:memory")
    assert detail.status_code == 200
    assert detail.json()["config_document"] == {
        "mcpServers": {"memory": body["mcpServers"]["memory"]}
    }


def test_integrations_create_a2a_and_detail(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_CONFIG_DIR", str(tmp_path / "mcp"))
    (tmp_path / "mcp").mkdir(parents=True)
    (tmp_path / "mcp" / "servers.json").write_text(
        '{"version": 1, "servers": []}\n', encoding="utf-8",
    )
    from src.platform.integrations import service as svc

    a2a = tmp_path / "a2a.json"
    acp = tmp_path / "acp.json"
    a2a.write_text('{"servers": {}}\n', encoding="utf-8")
    acp.write_text('{"agent_servers": {}}\n', encoding="utf-8")
    monkeypatch.setattr(svc, "a2a_config_path", lambda: a2a)
    monkeypatch.setattr(svc, "acp_config_path", lambda: acp)

    client = TestClient(app)
    created = client.post("/api/v1/integrations", json={
        "protocol": "A2A",
        "key": "review-agent",
        "url": "https://agents.example.com/review",
    })
    assert created.status_code == 200
    assert created.json()["connection"]["protocol"] == "A2A"
    assert created.json()["config_document"]["servers"]["review-agent"].startswith("https://")
