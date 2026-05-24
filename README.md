# Финансовый автопилот — локальный запуск

## Требования

| Инструмент | Версия | Установка |
|---|---|---|
| Python | 3.11 | `pyenv install 3.11.9` |
| Poetry | ≥1.8 | `pip install poetry` |
| Node.js | ≥18 | [nodejs.org](https://nodejs.org) |
| PostgreSQL | 14+ | [Postgres.app](https://postgresapp.com) |
| Redis | 7+ | `brew install redis` |

## Быстрый старт

### 1. Переменные окружения

```bash
cd backend
cp .env.example .env
# Отредактируй .env — укажи DATABASE_URL для твоего PostgreSQL
# Пример для Postgres.app без пароля:
# DATABASE_URL=postgresql+asyncpg://maximzugrov@localhost:5432/cfo_autopilot
```

```bash
cd frontend
cp .env.local.example .env.local
# NEXT_PUBLIC_API_URL=http://localhost:8000 (по умолчанию)
```

### 2. База данных

```bash
# Создать БД (если ещё не создана)
/Applications/Postgres.app/Contents/Versions/latest/bin/createdb cfo_autopilot

# Применить миграции
cd backend
DATABASE_URL=postgresql://maximzugrov@localhost:5432/cfo_autopilot \
  poetry run alembic upgrade head
```

### 3. Backend

```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload --port 8000
```

Проверка:
- `http://localhost:8000/health` → `{"status":"ok","version":"0.1.0"}`
- `http://localhost:8000/docs` → Swagger UI

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Открой `http://localhost:3000` — появится форма входа/регистрации.

### 5. Redis (опционально — для ARQ worker)

```bash
# macOS
brew services start redis

# или вручную
redis-server &
```

### 6. ARQ worker (опционально — для фоновых задач)

```bash
cd backend
poetry run arq app.workers.settings.WorkerSettings
```

## Первый запуск (E2E)

Через Swagger (`/docs`) или curl:

```bash
# 1. Регистрация
TOKEN=$(curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@company.com","company_name":"Моя компания"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Загрузка выписки
curl -X POST http://localhost:8000/imports/bank \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@tests/fixtures/banks/sber_sample.csv" \
  -F "bank_key=sber"

# 3. Дашборд
curl http://localhost:8000/dashboard/today \
  -H "Authorization: Bearer $TOKEN"
```

## Pilot pack

Перед пилотом с клиентом:

- **Чеклист деплоя и dogfood:** [docs/PILOT.md](docs/PILOT.md)
- **Automated smoke (CI):**
  ```bash
  cd backend
  poetry run pytest ../tests/integration/test_pilot_smoke.py -v
  ```
- **Smoke живого API** (backend должен быть запущен):
  ```bash
  chmod +x scripts/pilot-smoke.sh
  ./scripts/pilot-smoke.sh
  # staging: BASE_URL=https://api.example.com ./scripts/pilot-smoke.sh
  ```

## Тесты

```bash
cd backend

# Unit тесты
poetry run pytest tests/unit/ -v

# Интеграционные тесты (требует запущенного PostgreSQL)
DATABASE_URL=postgresql+asyncpg://maximzugrov@localhost:5432/cfo_autopilot \
  poetry run pytest ../tests/integration/ -v
```

## Структура проекта

```
cfo_autopilot/
├── backend/          # FastAPI, SQLAlchemy, Alembic, ARQ
│   ├── app/
│   │   ├── core/     # config, database, auth, audit, rbac
│   │   ├── models/   # SQLAlchemy ORM models
│   │   ├── routers/  # API endpoints
│   │   ├── services/ # ingestion, forecast, signals, explain, llm
│   │   └── workers/  # ARQ background tasks
│   └── alembic/      # migrations
├── frontend/         # Next.js 14, Tailwind CSS
│   └── src/
│       ├── app/      # pages (page.tsx = dashboard + auth)
│       ├── components/
│       └── lib/      # api.ts client
├── bot/              # aiogram Telegram digest bot
├── tests/
│   ├── unit/         # parsers, forecast engine, signals
│   ├── integration/  # tenant isolation, idempotency, dashboard
│   └── fixtures/     # CSV sample files
└── docs/
    └── adr/          # Architectural Decision Records
```

## ADR

- [ADR-0001](docs/adr/ADR-0001.md) — Monorepo FastAPI + Next.js
- [ADR-0002](docs/adr/ADR-0002.md) — PostgreSQL RLS для multi-tenancy
- [ADR-0003](docs/adr/ADR-0003.md) — ARQ (Redis) для background jobs
- [ADR-0004](docs/adr/ADR-0004.md) — LLM: OpenRouter (Claude) + YandexGPT fallback
- [ADR-0005](docs/adr/ADR-0005.md) — aiogram 3.x для Telegram bot
