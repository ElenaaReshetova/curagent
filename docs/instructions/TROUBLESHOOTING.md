# Диагностика: сообщение отправлено, ответ не пришёл

## Быстрая проверка

Выполните по очереди и найдите, где цепочка рвётся.

### 1. Задача попала в Kafka?

```bash
# Список топиков
docker compose exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic tasks --from-beginning --max-messages 5 --timeout-ms 5000
```

Если после отправки сообщения в чат здесь ничего не появляется — проблема в Chat Gateway или подключении к Kafka.

### 2. Task Manager видит агента и забирает задачу?

```bash
docker compose logs task_manager --tail 50
```

Ожидаемо:
- `Task Manager started`
- `Consumed task ... from Kafka` — задача взята из очереди
- `Task ... assigned to http://agent:8000` — задача назначена агенту

Если нет `Consumed task` — либо агент не free (Task Manager не читает Kafka, пока агент занят), либо в Kafka нет сообщений. Проверьте: `curl http://localhost:8000/health` → должен быть `{"status":"free"}`.

Для детальных логов: `DEBUG_TASK_MANAGER=1 docker compose up -d task_manager`

### 3. Агент получает задачу и обращается к LM Studio?

```bash
docker compose logs agent --tail 100
```

Ожидаемо:
- `Task execution failed` — ошибка при выполнении (часто LM Studio)
- Или отсутствие ошибок — задача выполняется

### 4. LM Studio доступен агенту?

Агент в Docker обращается к LM Studio по `host.docker.internal:1234`.

Проверка с хоста:
```bash
curl http://localhost:1234/v1/models
```

Должен вернуться JSON со списком моделей. Если ошибка — LM Studio не запущен или сервер не включён.

### 5. Имя модели совпадает с LM Studio?

В LM Studio откройте загруженную модель и посмотрите её ID (например, `llama-3.2-3b-instruct`).

Задайте его в `docker-compose.yml`:
```yaml
agent:
  environment:
    LM_STUDIO_MODEL: "llama-3.2-3b-instruct"  # ваш ID модели
```

Перезапустите: `docker compose up -d agent`

### 6. Агент может вызвать callback Chat Gateway?

В Docker callback: `http://chat_gateway:8080/api/callback`. Оба сервиса в одной сети.

Проверка из контейнера агента:
```bash
docker compose exec agent curl -s -o /dev/null -w "%{http_code}" http://chat_gateway:8080/
```

Ожидаемо: `200`.

### 7. Чат делает polling?

Чат опрашивает `/api/sessions/{id}/messages` каждые 2 секунды. Ответы должны появляться автоматически. Обновите страницу, если интерфейс завис.

---

## Slack: бот не берёт задачи

### Ошибка `missing_scope` в логах slack_gateway

Если видите `'error': 'missing_scope', 'needed': 'im:read'` или `'needed': 'im:history'`:

1. Откройте [api.slack.com/apps](https://api.slack.com/apps) → ваше приложение → **OAuth & Permissions**
2. Добавьте недостающие scopes: `im:read`, `im:history` (для DM)
3. **Reinstall to Workspace** — переустановите приложение (scopes применяются только после переустановки)
4. Перезапустите: `docker compose up -d slack_gateway`

### Бот не видит комментарий к выполненной задаче

1. **Комментарий должен быть Reply** — ответ в треде (нажмите Reply под сообщением), а не новое сообщение в канале.
2. **Старый тред** — бот проверяет последние 200 сообщений. Увеличьте `SLACK_HISTORY_LIMIT` в `.env` или docker-compose.
3. Пересоберите: `docker compose build slack_gateway --no-cache && docker compose up -d slack_gateway`

### Проверка цепочки

1. **Slack Gateway** — http://localhost:8090/api/slack/status: `poll_stats.tasks_produced` > 0?
2. **Task Manager** — логи: `Consumed task ... from Kafka (source=slack)`?
3. **Агент** — `curl http://localhost:8000/health` → `{"status":"free"}`?

Если `tasks_produced` растёт, но нет `Consumed task` — агент занят. Task Manager читает Kafka только когда агент free.

---

## Типичные причины

| Симптом | Причина | Решение |
|--------|---------|---------|
| Нет логов `assigned` в task_manager | Агент busy или недоступен | Проверить `GET http://localhost:8000/health` → `{"status":"free"}` |
| `Task execution failed` в agent | LM Studio недоступен или ошибка модели | Запустить LM Studio, проверить `LM_STUDIO_MODEL` |
| `Connection refused` к LM Studio | Агент не доходит до хоста | На Mac/Windows: `host.docker.internal` должен работать; на Linux добавить `extra_hosts` |
| Callback не срабатывает | Агент не может достучаться до chat_gateway | Проверить сеть Docker, `CHAT_CALLBACK_BASE_URL` |
| Модель не отвечает | Неверный `LM_STUDIO_MODEL` | Указать точный ID модели из LM Studio |

---

## Локальный запуск (без Docker)

При локальном запуске все сервисы на `localhost`:

1. LM Studio: `http://localhost:1234`
2. Agent: `http://localhost:8000`
3. Chat Gateway: `http://localhost:8080`
4. `CHAT_CALLBACK_BASE_URL=http://localhost:8080` — чтобы callback шёл на локальный чат
