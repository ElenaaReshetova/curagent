# Platform data architecture

| Doc | Purpose |
|-----|---------|
| [PLATFORM_DATA_ARCHITECTURE.md](PLATFORM_DATA_ARCHITECTURE.md) | Target architecture (SoT, schemas, stores) |
| [CURRENT_DATA_ARCHITECTURE.md](CURRENT_DATA_ARCHITECTURE.md) | Inventory + gap analysis + migration progress |

## Local PostgreSQL (Playbooks)

```bash
docker compose up -d platform_db
export PLATFORM_DATABASE_URL=postgresql+psycopg://platform:platform@localhost:5433/platform
alembic upgrade head   # preferred
# or let the app create tables on first Playbooks API call (dev only)
```

Without `PLATFORM_DATABASE_URL`, Playbooks keep using JSON under `PLATFORM_CONFIG_DIR`.
Force JSON even with a DB URL: `PLAYBOOKS_STORE=json`.
