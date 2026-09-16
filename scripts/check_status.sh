#!/bin/bash
# Быстрая проверка состояния системы

echo "=== 1. LM Studio (localhost:1234) ==="
curl -s http://localhost:1234/v1/models 2>/dev/null | head -3 || echo "НЕ ДОСТУПЕН - запустите LM Studio с сервером"

echo ""
echo "=== 2. Agent health (localhost:8000) ==="
curl -s http://localhost:8000/health 2>/dev/null || echo "НЕ ДОСТУПЕН"

echo ""
echo "=== 3. Chat Gateway (localhost:8080) ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8080/ 2>/dev/null || echo "НЕ ДОСТУПЕН"

echo ""
echo "=== 4. Docker контейнеры ==="
docker compose ps 2>/dev/null || echo "Docker compose не запущен"

echo ""
echo "=== 5. Последние логи agent ==="
docker compose logs agent --tail 10 2>/dev/null || echo "—"

echo ""
echo "=== 6. Последние логи task_manager ==="
docker compose logs task_manager --tail 10 2>/dev/null || echo "—"
