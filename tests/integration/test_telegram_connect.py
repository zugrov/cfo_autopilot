"""Интеграционные тесты Telegram /connect flow."""
from __future__ import annotations

import pytest

from .conftest import auth_headers, _register


pytestmark = pytest.mark.asyncio


async def test_connect_code_requires_auth(client):
    resp = await client.post("/auth/me/telegram/connect-code")
    assert resp.status_code in (401, 403)


async def test_connect_code_returns_six_digits(client):
    user = await _register(client)
    resp = await client.post(
        "/auth/me/telegram/connect-code",
        headers=auth_headers(user["token"]),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["code"]) == 6
    assert data["code"].isdigit()
    assert data["ttl_seconds"] == 600


async def test_internal_set_telegram_rejects_without_secret(client):
    user = await _register(client)
    resp = await client.patch(
        "/auth/internal/set-telegram",
        json={"user_id": user["user_id"], "telegram_chat_id": "123456789"},
    )
    assert resp.status_code in (403, 503)


async def test_internal_set_telegram_with_valid_secret(client, monkeypatch):
    secret = "test-internal-secret"
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", secret)

    from app.core.config import get_settings
    get_settings.cache_clear()

    user = await _register(client)
    resp = await client.patch(
        "/auth/internal/set-telegram",
        json={"user_id": user["user_id"], "telegram_chat_id": "987654321"},
        headers={"X-Internal-Secret": secret},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ok"

    get_settings.cache_clear()
