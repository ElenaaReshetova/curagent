# Integrations — CURRENT STATE

**Date:** 2026-07-19  
**Spec:** [INTEGRATIONS_SYSTEM_REQUIREMENTS.md](INTEGRATIONS_SYSTEM_REQUIREMENTS.md)  
**UI:** `src/workflow_ui/static/integrations/`

## Current

| Area | Location | Notes |
|------|----------|-------|
| Nav | `data-view=integrations` | Dedicated module |
| Catalog / JSON | `integrations/module.js` | Cards + standard config.json editor |
| Domain | `src/platform/integrations/` | MCP / A2A / ACP only |
| API | `/api/v1/integrations*` | Catalog, detail, config get/put, upsert, delete |
| MCP source | `config/mcp/servers.json` | Exported as `{ "mcpServers": … }` |
| A2A / ACP | `config/integrations/a2a.json`, `acp.json` | `servers` / `agent_servers` |

## Principle

Интеграции — только протокольные подключения:

- **MCP** — tools/context (`mcpServers` как в Claude Desktop / Cursor)
- **A2A** — agent-to-agent (`servers` alias → URL)
- **ACP** — Agent Client Protocol (`agent_servers`)

Legacy connector catalog (Jira OAuth wizard и т.п.) убран из UI.
