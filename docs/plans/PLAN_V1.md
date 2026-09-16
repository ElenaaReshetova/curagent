# План работ v1

**Версия:** 1.0  
**Дата:** 2025-03-07

## Этапы

### Этап 1: Документация и каркас

- [x] Создать `docs/` с подпапками и первой версией требований, архитектуры и плана
- [x] Инициализировать venv, `requirements.txt`, структуру `src/`

### Этап 2: Модуль агента

- [x] Настроить OpenAI Agents SDK с LM Studio (base_url)
- [x] Реализовать загрузку Skills из `skills/`
- [x] Подключить MCP / function tool для callback в чат
- [x] FastAPI: `/health` (busy/free), `POST /task`
- [x] Dockerfile для агента

### Этап 3: Task Manager

- [x] Kafka consumer (aiokafka)
- [x] Конфиг списка URL агентов
- [x] Цикл: опрос healthcheck → consume → POST /task
- [x] Dockerfile

### Этап 4: Chat Gateway

- [x] REST API для создания задачи + запись в Kafka
- [x] Простой веб-интерфейс чата (HTML/JS)
- [x] HTTP callback endpoint для ответов от агента

### Этап 5: Интеграция

- [x] docker-compose: Kafka, Agent, Task Manager, Chat Gateway
- [x] Инструкции по развёртыванию в `docs/instructions/`
