"""
Тест dashboard: после загрузки CSV возвращает данные с балансом и forecast.
"""
import pytest

from .conftest import _register, auth_headers, FIXTURES_DIR


pytestmark = pytest.mark.asyncio


async def test_dashboard_with_data(client):
    """После импорта dashboard возвращает has_data=True, balance и forecast."""
    user = await _register(client, company="Dashboard Test Co")
    csv_path = f"{FIXTURES_DIR}/sber_sample.csv"

    with open(csv_path, "rb") as f:
        resp = await client.post(
            "/imports/bank",
            headers=auth_headers(user["token"]),
            files={"file": ("sber_sample.csv", f, "text/csv")},
            data={"bank_key": "sber"},
        )
    assert resp.status_code == 201, resp.text

    resp_d = await client.get(
        "/dashboard/today",
        headers=auth_headers(user["token"]),
    )
    assert resp_d.status_code == 200
    data = resp_d.json()

    assert data["has_data"] is True, "Dashboard не показывает данные после импорта"
    assert data["balance"] is not None, "Balance is None"
    assert isinstance(data["balance"], (int, float))
    assert data["forecast"] is not None, "Forecast is None"
    assert "days_preview" in data["forecast"]
    assert len(data["forecast"]["days_preview"]) > 0


async def test_dashboard_empty_before_import(client):
    """Новая компания без импорта видит has_data=False."""
    user = await _register(client, company="Empty Dashboard Co")

    resp = await client.get(
        "/dashboard/today",
        headers=auth_headers(user["token"]),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_data"] is False
    assert data["balance"] is None


async def test_dashboard_unauthorized(client):
    """Без токена — 403."""
    resp = await client.get("/dashboard/today")
    assert resp.status_code == 403
