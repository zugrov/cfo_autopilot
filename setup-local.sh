#!/usr/bin/env bash
# setup-local.sh — запуск cfo_autopilot локально
# Статус: Python 3.11.9 и Poetry уже установлены, frontend npm-пакеты готовы
# Осталось: поднять PostgreSQL + Redis, применить миграции, стартовать сервисы
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
POETRY="$HOME/.local/bin/poetry"
PYTHON311="$HOME/.pyenv/versions/3.11.9/bin/python3.11"

# ─── ШАГИ ПОДГОТОВКИ БД (выбери один вариант) ───────────────────────────────
# Вариант A — Docker Desktop (рекомендуется, один раз скачать с docker.com):
#   docker compose up -d postgres redis
#
# Вариант B — Postgres.app (GUI, без brew/docker):
#   1. Скачать: https://postgresapp.com/
#   2. Перетащить в Applications, нажать Initialize
#   3. brew services start redis  ИЛИ  redis-server --daemonize yes
#
# Вариант C — Homebrew (если уже установлен):
#   brew install postgresql@16 redis
#   brew services start postgresql@16
#   brew services start redis
#   createdb cfo_autopilot
# ─────────────────────────────────────────────────────────────────────────────

echo "==> Проверяем PostgreSQL..."
if ! pg_isready -h localhost -p 5432 -q 2>/dev/null; then
  echo "PostgreSQL не найден на localhost:5432"
  echo "Запусти один из вариантов выше и перезапусти этот скрипт"
  exit 1
fi

echo "==> Проверяем Redis..."
if ! redis-cli ping &>/dev/null; then
  echo "Redis не найден. Запусти redis-server и перезапусти скрипт"
  exit 1
fi

echo "==> Создаём БД (если не существует)..."
createdb cfo_autopilot 2>/dev/null || echo "  БД уже существует"

echo "==> Применяем миграции..."
cd "$SCRIPT_DIR/backend"
"$POETRY" run alembic upgrade head

echo ""
echo "✓ Всё готово! Запускай в двух терминалах:"
echo ""
echo "  Терминал 1 (backend):"
echo "    cd backend"
echo "    ~/.local/bin/poetry run uvicorn app.main:app --reload --port 8000"
echo ""
echo "  Терминал 2 (frontend — уже запущен):"
echo "    cd frontend && npm run dev"
echo ""
echo "  API docs: http://localhost:8000/docs"
echo "  Frontend: http://localhost:3000"
