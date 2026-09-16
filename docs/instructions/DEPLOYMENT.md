# Инструкции по развёртыванию

**Версия:** 1.0  
**Дата:** 2025-03-07

## Требования

- Docker и Docker Compose
- LM Studio (запущен на хосте с загруженной моделью)
- Python 3.9+ (для локальной разработки)

## Быстрый старт (Docker Compose)

### 1. Запустите LM Studio

1. Установите [LM Studio](https://lmstudio.ai/)
2. Загрузите модель (например, Llama, Mistral)
3. Запустите локальный сервер (по умолчанию порт 1234)
4. **Важно:** Запомните ID модели (виден в LM Studio). Задайте его в `docker-compose.yml`:
   ```yaml
   agent:
     environment:
       LM_STUDIO_MODEL: "ваш-id-модели"  # например llama-3.2-3b-instruct
   ```

### 2. Запустите систему

```bash
cd auto_agent
docker compose up -d
```

Сервисы:

| Сервис              | Порт | Описание                                      |
|---------------------|------|-----------------------------------------------|
| Chat Gateway        | 8080 | Веб-чат, API задач                            |
| **Workflow UI**     | 8092 | **Visual editor графов шагов pipeline**       |
| Temporal UI         | 8088 | Мониторинг multi-agent workflows              |
| Slack Gateway       | 8090 | Опрос Slack, callback для ответов             |
| Jira Gateway        | 8091 | Опрос Jira, callback для ответов              |
| Orchestrator Worker | —    | Temporal worker (Executor, Verifier, Publisher) |
| Task Manager        | —    | Kafka → Temporal workflow starter             |
| Agent (legacy)      | 8000 | Прямой POST /task (опционально)               |
| Temporal            | 7233 | Orchestrator backend                          |
| Kafka        | 9092 | Очередь задач               |
| Zookeeper    | 2181 | Для Kafka                   |

### 3. Откройте чат

Перейдите в браузере: http://localhost:8080

Введите задачу — она попадёт в Kafka, Task Manager запустит Temporal workflow, orchestrator worker выполнит pipeline и отправит результат в чат.

**Temporal UI:** http://localhost:8088 — мониторинг workflows, retry, история.

**Workflow UI:** http://localhost:8092 — визуальный редактор графа шагов (drag-and-drop, connect, save). Изменения применяются к новым задачам через default template.

Pipeline: `normalize → classify → plan → execute → verify → compliance → publish`

## Локальная разработка (без Docker)

### 1. Создайте venv и установите зависимости

```bash
cd auto_agent
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Запустите Kafka (через Docker)

```bash
docker compose up -d zookeeper kafka
```

### 3. Запустите LM Studio

Запустите LM Studio и загрузите модель на порту 1234.

### 4. Запустите сервисы в отдельных терминалах

**Терминал 1 — Agent:**
```bash
export LM_STUDIO_URL=http://localhost:1234/v1
export LM_STUDIO_MODEL=local-model
python -m uvicorn src.agent.api.main:app --host 0.0.0.0 --port 8000
```

**Терминал 2 — Task Manager:**
```bash
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export AGENT_URLS=http://localhost:8000
python -m src.task_manager.main
```

**Терминал 3 — Chat Gateway:**
```bash
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export CHAT_CALLBACK_BASE_URL=http://localhost:8080
python -m uvicorn src.chat_gateway.main:app --host 0.0.0.0 --port 8080
```

### 5. Откройте чат

http://localhost:8080

## Переменные окружения

### Agent

| Переменная      | По умолчанию              | Описание                          |
|-----------------|---------------------------|-----------------------------------|
| LM_STUDIO_URL   | http://localhost:1234/v1  | URL LM Studio API                 |
| LM_STUDIO_MODEL | local-model               | Имя модели в LM Studio            |
| SKILLS_DIR      | —                         | Путь к Skills (или несколько через запятую). Если не задан — используются `skills/`, `.claude/skills/` и `~/.claude/skills/` |
| SKILLS_INCLUDE_USER    | true  | Загружать Skills из `~/.claude/skills/` |
| SKILLS_INCLUDE_PROJECT | true  | Загружать Skills из `skills/` и `.claude/skills/` |
| SLACK_BOT_TOKEN | —                         | Для MCP Slack: Bot Token (xoxb-*). Если задан — агент отвечает в Slack через MCP (`slack_reply_to_thread`), а не через HTTP callback |
| SLACK_TEAM_ID   | —                         | Team ID (начинается с T) для MCP Slack |
| SLACK_CHANNEL_IDS | —                       | Опционально: ID каналов через запятую для MCP Slack |
| JIRA_BASE_URL   | —                         | Для MCP Jira: URL инстанса (например https://your-domain.atlassian.net) |
| JIRA_USER_EMAIL | —                        | Email учётной записи Jira |
| JIRA_API_TOKEN  | —                         | API токен Jira Cloud |
| JIRA_TYPE       | cloud                     | `cloud` или `server` для Jira Server/Data Center |

### Task Manager

| Переменная              | По умолчанию        | Описание                    |
|-------------------------|---------------------|-----------------------------|
| KAFKA_BOOTSTRAP_SERVERS | localhost:9092      | Адреса брокеров Kafka      |
| KAFKA_TASKS_TOPIC       | tasks               | Топик задач                |
| AGENT_URLS              | http://localhost:8000 | URL агентов (через запятую) |
| TASK_MANAGER_POLL_INTERVAL | 5               | Интервал опроса (сек)       |

### Chat Gateway

| Переменная           | По умолчанию        | Описание                    |
|----------------------|---------------------|-----------------------------|
| KAFKA_BOOTSTRAP_SERVERS | localhost:9092  | Адреса брокеров Kafka      |
| KAFKA_TASKS_TOPIC    | tasks               | Топик задач                |
| CHAT_CALLBACK_BASE_URL | http://localhost:8080 | Базовый URL для callback |

### Slack Gateway

| Переменная           | По умолчанию        | Описание                    |
|----------------------|---------------------|-----------------------------|
| KAFKA_BOOTSTRAP_SERVERS | kafka:29092     | Адреса брокеров Kafka      |
| KAFKA_TASKS_TOPIC    | tasks               | Топик задач                |
| SLACK_BOT_TOKEN      | —                   | **Обязательно.** Bot Token (xoxb-*) из Slack App |
| SLACK_BOT_NAME       | My MCP Bot          | Имя бота (для логов)       |
| SLACK_CALLBACK_BASE_URL | http://slack_gateway:8090 | URL для callback (используется Slack Gateway; агент при source=slack отвечает через MCP, не через callback) |
| SLACK_POLL_INTERVAL  | 30                  | Интервал опроса Slack (сек) |
| SLACK_REACTION_COMPLETED | white_check_mark | Эмодзи реакции «взято в работу» |
| DEBUG_SLACK_POLL        | 0                | 1 — подробные логи опроса (для отладки) |

**Диагностика «бот не берёт задачи»:** откройте http://localhost:8090/api/slack/status — там `poll_stats` (сколько задач отправлено, последний опрос, ошибки). Запустите с `DEBUG_SLACK_POLL=1` для детальных логов.

**Настройка Slack App:**

1. Создайте приложение на [api.slack.com/apps](https://api.slack.com/apps)
2. Добавьте OAuth Scopes (обязательно все):
   - `channels:history`, `channels:read` — публичные каналы
   - `groups:read`, `groups:history` — приватные каналы и треды
   - `im:read`, `im:history` — **DM (без них бот не видит личные сообщения)**
   - `chat:write`, `reactions:write`, `users:read`
3. Установите приложение в workspace, скопируйте Bot Token. **После добавления scopes — переустановите** (Reinstall to Workspace)
4. Добавьте бота в каналы, где нужны задачи (или пишите в DM)
5. Запустите с `SLACK_BOT_TOKEN=xoxb-... docker compose up -d`

**Работа через комментарии:** бот читает не только основное сообщение, но и все комментарии в треде. **Важно:** оставляйте комментарии как ответ (Reply) в треде — отдельные сообщения в канале без @упоминания бот не увидит. Можно добавлять комментарии к уже выполненной задаче — бот возьмёт её в работу с учётом новых комментариев. `SLACK_HISTORY_LIMIT` (по умолчанию 200) — сколько сообщений истории проверять; если тред старый, увеличьте.

**Ответы в Slack:** агент отправляет ответы через MCP (`slack_reply_to_thread`), а не через HTTP callback. Для этого агенту нужны `SLACK_BOT_TOKEN` и `SLACK_TEAM_ID` (те же, что у Slack Gateway). В `docker-compose` они передаются в оба сервиса.

**Диагностика:** если бот не видит каналы, откройте http://localhost:8090/api/slack/status — там будет список каналов, где бот участник, и подсказки.

### Jira Gateway

| Переменная           | По умолчанию        | Описание                    |
|----------------------|---------------------|-----------------------------|
| KAFKA_BOOTSTRAP_SERVERS | kafka:29092     | Адреса брокеров Kafka      |
| KAFKA_TASKS_TOPIC    | tasks               | Топик задач                |
| JIRA_BASE_URL        | —                   | **Обязательно.** URL Jira (например https://nickolaj95.atlassian.net) |
| JIRA_USER_EMAIL      | —                   | **Обязательно.** Email учётной записи (бот должен быть назначен на задачи) |
| JIRA_API_TOKEN       | —                   | **Обязательно.** API токен Jira Cloud |
| JIRA_PROJECT         | CUR                 | Ключ проекта (из URL board) |
| JIRA_CALLBACK_BASE_URL | http://jira_gateway:8091 | URL для callback |
| JIRA_POLL_INTERVAL   | 60                  | Интервал опроса (сек) |
| DEBUG_JIRA_POLL      | 0                   | 1 — подробные логи опроса |

**Настройка Jira:** создайте API токен на [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens). Учётная запись (JIRA_USER_EMAIL) должна быть назначена на задачи в проекте CUR — Jira Gateway опрашивает `assignee=currentUser()` и создаёт задачи в Kafka. Ответ агента добавляется как комментарий к тикету через MCP `add_comment` или HTTP callback.

**Диагностика:** http://localhost:8091/api/jira/status — poll_stats, обработанные тикеты.

**Jira MCP:** агент получает доступ к Jira через MCP (search_issues, get_issue, create_issue, update_issue, add_comment и др.) при наличии JIRA_* переменных в агенте.

## Добавление Skills (Anthropic-style)

Агент поддерживает локальные Skills в формате Anthropic. Skills загружаются из:

1. **Проект:** `skills/` или `.claude/skills/` (относительно корня проекта)
2. **Пользователь:** `~/.claude/skills/`
3. **Кастомный путь:** переменная `SKILLS_DIR` (один путь или несколько через запятую)

Структура:

```
skills/                    # или .claude/skills/
├── general/
│   └── SKILL.md
└── my-skill/
    └── SKILL.md
```

Формат SKILL.md — YAML frontmatter + Markdown (совместим с Anthropic):

```yaml
---
name: my-skill
description: Краткое описание. Используй при работе с X, Y или когда пользователь упоминает Z.
---

# My Skill

## Инструкции
...
```

Поля `name` и `description` обязательны. `description` помогает агенту понять, когда применять Skill.

## Устранение неполадок

Подробная диагностика: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

### Агент не получает ответ от LM Studio

- Убедитесь, что LM Studio запущен и модель загружена
- В Docker: используйте `host.docker.internal` для доступа к хосту
- Проверьте: `curl http://localhost:1234/v1/models`

### Задачи не выполняются

- Проверьте логи Task Manager: `docker compose logs task_manager`
- Проверьте, что Kafka создала топик: `docker compose exec kafka kafka-topics --list --bootstrap-server localhost:9092`
- Убедитесь, что агент возвращает `free` в `/health`

### Ответы не появляются в чате

- Убедитесь, что CHAT_CALLBACK_BASE_URL доступен агенту (в Docker: `http://chat_gateway:8080`)
- Проверьте логи агента на ошибки при вызове send_to_chat
