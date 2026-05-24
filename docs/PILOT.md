# Pilot pack — чеклист деплоя и dogfood

Руководство для запуска пилота с первым живым клиентом.

## A. Pre-flight checklist (переменные окружения)

### Обязательные

| Переменная | Где | Назначение |
|------------|-----|------------|
| `DATABASE_URL` | backend `.env` | PostgreSQL (asyncpg) |
| `JWT_SECRET` | backend `.env` | Подпись токенов (не `change-me` в prod) |
| `NEXT_PUBLIC_API_URL` | frontend `.env.local` | URL backend для браузера |

### Рекомендуемые для полного MVP

| Переменная | Назначение |
|------------|------------|
| `REDIS_URL` | ARQ worker: пересчёт снапшотов, Telegram/weekly cron |
| `OPENROUTER_API_KEY` | AI-чат (primary) |
| `YANDEX_GPT_API_KEY`, `YANDEX_GPT_FOLDER_ID` | AI fallback |
| `TELEGRAM_BOT_TOKEN` | Ежедневный Telegram-дайджест |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Email PDF-отчёт по понедельникам |

Шаблон: [`backend/.env.example`](../backend/.env.example), [`frontend/.env.local.example`](../frontend/.env.local.example).

---

## B. Deploy checklist (VPS / Yandex Cloud / Selectel)

- [ ] **Postgres 16** — создана БД `cfo_autopilot`
- [ ] **Redis 7** — доступен worker-у
- [ ] **Миграции:** `cd backend && poetry run alembic upgrade head`
- [ ] **Backend:** `uvicorn app.main:app --host 0.0.0.0 --port 8000` (prod: gunicorn + uvicorn workers)
- [ ] **Worker:** `arq app.workers.settings.WorkerSettings` (отдельный процесс)
- [ ] **Frontend:** `npm run build && npm start` (или reverse proxy на static)
- [ ] **Health:** `curl https://your-api/health` → `{"status":"ok"}`
- [ ] **Smoke API:** `./scripts/pilot-smoke.sh` с `BASE_URL=https://your-api`
- [ ] **CORS:** в [`backend/app/main.py`](../backend/app/main.py) добавлен prod-origin frontend
- [ ] **Secrets:** JWT, LLM, Telegram, SMTP — только в env, не в git

### Локальная подготовка

```bash
./setup-local.sh   # Postgres + Redis + мигraции
```

---

## C. Automated smoke

### Integration test (CI, без поднятого сервера)

```bash
cd backend
poetry run pytest ../tests/integration/test_pilot_smoke.py -v
```

AI-тест `test_pilot_ai_chat` пропускается без `OPENROUTER_API_KEY`.

### Live API (staging / prod)

```bash
chmod +x scripts/pilot-smoke.sh

# Локально (backend на :8000)
./scripts/pilot-smoke.sh

# Staging
BASE_URL=https://api.staging.example.com ./scripts/pilot-smoke.sh
```

Проверяет: register → import CSV → dashboard → obligations → team → audit → PDF.

---

## D. Dogfood-сценарий (~15 мин, ручной UI)

Откройте frontend (обычно `http://localhost:3000`). Отмечайте pass/fail для пилотной сессии с клиентом.

| # | Шаг | Pass |
|---|-----|------|
| 1 | **Регистрация** — email + название компании, вход без ошибок | ☐ |
| 2 | **Onboarding** — загрузка CSV банковской выписки (Сбер/Tinkoff) без инструкции разработчика | ☐ |
| 3 | **Dashboard** — остаток, прогноз 30+ дней, сигнал дефицита (если есть данные) | ☐ |
| 4 | **Обязательства** — создать платёж, виден в списке | ☐ |
| 5 | **Операции** — drill-down в транзакции из дашборда | ☐ |
| 6 | **AI-чат** — типовой вопрос (напр. «Когда кассовый разрыв?»), ответ с цифрами | ☐ |
| 7 | **Команда** — пригласить viewer, появился в списке | ☐ |
| 8 | **Журнал** — запись «Приглашение пользователя» | ☐ |
| 9 | **PDF** — «Скачать отчёт», файл открывается | ☐ |
| 10 | *(опц.)* **Telegram** — код привязки, `/connect` в боте | ☐ |

### Критерии успеха пилота

- Клиент загружает выписку сам
- Видит свои деньги и прогноз за 3 минуты
- Доверяет цифрам (можно провалиться в операции)
- Owner управляет командой и видит журнал

---

## E. Известные ограничения MVP

- Один tenant = одна компания на регистрацию
- AI без LLM-ключей недоступен
- Email PDF без SMTP — только download
- Telegram digest без `TELEGRAM_BOT_TOKEN` — только UI
- Docker Compose без auto-migrate — миграции вручную (см. README)
