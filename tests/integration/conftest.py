"""
Интеграционные тесты: запускаются против реальной БД (cfo_autopilot).
Требуют: Postgres.app запущен, DATABASE_URL в .env или переменная окружения.

Запуск:
  cd backend
  DATABASE_URL=postgresql+asyncpg://maximzugrov@localhost:5432/cfo_autopilot \
    poetry run pytest ../tests/integration/ -v
"""
import asyncio
import os
import sys
import uuid
import pytest
import pytest_asyncio

# Добавляем backend в PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from httpx import AsyncClient, ASGITransport

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://maximzugrov@localhost:5432/cfo_autopilot",
)
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "")

from app.main import app  # noqa: E402

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "../fixtures/banks")


@pytest.fixture(scope="session")
def event_loop():
    """Один event loop на всю тестовую сессию — избегаем проблем с connection pool."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
    asyncio.set_event_loop(None)


@pytest_asyncio.fixture(scope="session")
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def _register(client: AsyncClient, email: str | None = None, company: str = "Test Co") -> dict:
    """Регистрирует нового пользователя и возвращает {token, company_id, user_id}."""
    email = email or f"test_{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/auth/register",
        json={"email": email, "company_name": company},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return {
        "token": data["access_token"],
        "company_id": data["company_id"],
        "user_id": data["user_id"],
        "email": email,
    }


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
