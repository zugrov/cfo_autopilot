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

    # Sprint A: alerts удалён из ответа
    assert "alerts" not in data, "alerts[] должен быть удалён из API (f1)"

    # Sprint 2: stress-сценарий
    assert "days_stress" in data["forecast"], "days_stress отсутствует"

    # Sprint 2: объяснение
    assert "explain" in data and data["explain"] is not None
    assert "reasons" in data["explain"]

    # Sprint 2: минимум 90 дней прогноза
    assert len(data["forecast"]["days_preview"]) >= 90, "Прогноз должен быть не менее 90 дней"

    # Sprint A: deficit_signal содержит severity если есть
    ds = data["forecast"].get("deficit_signal")
    if ds is not None:
        assert "severity" in ds, "deficit_signal должен содержать severity"
        assert ds["severity"] in ("critical", "warning", "info")
        assert "days_until" in ds


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
