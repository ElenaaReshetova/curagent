# Slack MCP Server

Локальная копия [@modelcontextprotocol/server-slack](https://www.npmjs.com/package/@modelcontextprotocol/server-slack) для интеграции Slack с Cursor.

## Подключение в Cursor

1. **Создай Slack App** на [api.slack.com/apps](https://api.slack.com/apps):
   - Create New App → From scratch
   - Выбери workspace

2. **Добавь Bot Token Scopes** (OAuth & Permissions):
   - `channels:history` — просмотр сообщений в публичных каналах
   - `channels:read` — информация о каналах
   - `chat:write` — отправка сообщений
   - `reactions:write` — эмодзи-реакции
   - `users:read` — список пользователей
   - `users.profile:read` — профили пользователей

3. **Установи приложение** в workspace и скопируй **Bot User OAuth Token** (начинается с `xoxb-`).

4. **Узнай Team ID** — [инструкция](https://slack.com/help/articles/221769328-Locate-your-Slack-URL-or-ID#find-your-workspace-or-org-id) (начинается с `T`).

5. **Обнови `.cursor/mcp.json`** — подставь свои значения:
   ```json
   "env": {
     "SLACK_BOT_TOKEN": "xoxb-твой-токен",
     "SLACK_TEAM_ID": "T01234567",
     "SLACK_CHANNEL_IDS": "C01234567,C76543210"
   }
   ```
   - `SLACK_CHANNEL_IDS` (опционально) — ID каналов через запятую. Если пусто — доступны все публичные каналы.

6. **Перезапусти Cursor** полностью.

7. **Проверь** в Settings → Tools & MCP — сервер `slack` должен быть в списке.

## Доступные инструменты

- `slack_list_channels` — список каналов
- `slack_post_message` — отправить сообщение
- `slack_reply_to_thread` — ответ в треде
- `slack_add_reaction` — добавить реакцию
- `slack_get_channel_history` — история канала
- `slack_get_thread_replies` — ответы в треде
- `slack_get_users` — список пользователей
- `slack_get_user_profile` — профиль пользователя
