# Current Data Architecture

**Date:** 2026-07-17  
**Target:** [PLATFORM_DATA_ARCHITECTURE.md](PLATFORM_DATA_ARCHITECTURE.md)  
**Scope:** Inventory of how data is stored today + gap analysis vs target.  
**Rule:** Do not rewrite the entire persistence layer in one step. Migrate module-by-module, starting with Playbooks.

---

## 0. Migration progress (2026-07-19)

| Item | Status |
|------|--------|
| `PLATFORM_DATABASE_URL` + SQLAlchemy/Alembic/psycopg | **Done** |
| Compose service `platform_db` (:5433) | **Done** |
| Tables `workspaces`, `playbooks`, `playbook_versions`, `playbook_nodes`, `playbook_transitions` | **Done** (Alembic `001` / `002`) |
| Tables `skills`, `skill_versions` | **Done** (Alembic `003_skills`) |
| Playbooks + Skills repository: PG SoT when URL set | **Done** |
| Optimistic locking (`revision` / 409) on PG path | **Done** |
| Overview / dashboard use versioned catalogs (not governed-flat) | **Done** |
| Default when no DB URL | JSON versioned fallback (`PLAYBOOKS_STORE=json` / `SKILLS_STORE=json`) |
| Other modules on PG | Not started |

```bash
export PLATFORM_DATABASE_URL=postgresql+psycopg://platform:platform@localhost:5433/platform
alembic upgrade head
```

---

## 1. Executive summary

| Layer | Current reality |
|-------|-----------------|
| Business SoT | **PostgreSQL for Playbooks + Skills** when `PLATFORM_DATABASE_URL` is set; JSON versioned records otherwise; other modules still under `config/platform/` |
| App DB | `platform_db` + SQLAlchemy 2 / Alembic |
| Temporal Postgres | Separate Compose service (orchestration only) |
| YAML packages | Not present as standalone manifests |
| Object storage / Redis / Vector | Missing (knowledge search is stub) |
| Kafka | Task ingress (`tasks`) |
| UI → storage | `/api/v1` only — never direct DB/files |

Playbooks path with DB:

```text
UI → /api/v1/playbooks* → service → repository → PostgreSQL
     (graph_json + playbook_nodes + playbook_transitions, one transaction)
```

---

## 2. Database technology

| Item | Status |
|------|--------|
| `PLATFORM_DATABASE_URL` | Optional; enables Playbooks PG SoT |
| SQLAlchemy 2 / Alembic / psycopg3 | In `requirements.txt` |
| Code | `src/platform/db/`, `src/platform/playbooks/repository.py` |
| Migrations | `alembic/versions/001_workspaces_playbooks.py` |

---

## 3. Tables and collections

### PostgreSQL (Playbooks)

| Table | Role |
|-------|------|
| `workspaces` | Default workspace |
| `playbooks` | Entity + published/draft pointers |
| `playbook_versions` | Lifecycle + `graph_json` + bindings |
| `playbook_nodes` | Normalized nodes (`position_json` UI-only) |
| `playbook_transitions` | Normalized edges |

### JSON (other modules + Playbooks fallback)

Versioned: skills, rules, flows, runtime profiles, controls, integrations, executions, knowledge, human checkpoints under `config/platform/`. Legacy flat catalogs still via `store.py`.

---

## 4. Gap summary

| Target | Gap |
|--------|-----|
| All entities in PG | Playbooks + Skills (+ workspace); others still JSON |
| YAML package import | Missing |
| Object storage / vector / outbox | Missing |
| Full IAM | Default workspace only |

**Next:** Rules/Flows on PG (same Entity/Version pattern), then outbox on publish.

---

## 5. Definition of done (partial)

- [x] Playbooks PostgreSQL SoT (env-gated)  
- [x] Skills PostgreSQL SoT (env-gated)  
- [x] Draft vs published + revision locking  
- [x] graph_json + normalized tables same transaction  
- [ ] YAML / object storage / vector / outbox  
- [x] Playbooks + Skills tests (JSON + SQLite/PG path)

See also [README.md](README.md) and [../playbooks/CURRENT_STATE.md](../playbooks/CURRENT_STATE.md).
