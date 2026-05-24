"""
Тест dashboard: после загрузки CSV возвращает данные с балансом и forecast.
"""
import os
import pytest
from pathlib import Path

from .conftest import _register, auth_headers, FIXTURES_DIR

ONEC_FIXTURES = Path(__file__).parent.parent / "fixtures" / "onec"


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


async def test_dashboard_with_onec_receivables(client):
    """После импорта aging ОСВ дашборд показывает receivables + has_aging_detail."""
    user = await _register(client, company="OnecDashCo")
    headers = auth_headers(user["token"])

    # Сначала банк (нужен баланс для снапшота)
    csv_path = f"{FIXTURES_DIR}/sber_sample.csv"
    with open(csv_path, "rb") as f:
        r = await client.post(
            "/imports/bank",
            headers=headers,
            files={"file": ("sber_sample.csv", f, "text/csv")},
            data={"bank_key": "sber"},
        )
    assert r.status_code == 201

    # Затем 1С ОСВ aging
    aging_bytes = (ONEC_FIXTURES / "osv_aging_sample.csv").read_bytes()
    r2 = await client.post(
        "/imports/onec",
        headers=headers,
        files={"file": ("osv_aging_sample.csv", aging_bytes, "text/csv")},
    )
    assert r2.status_code == 201

    resp = await client.get("/dashboard/today", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["has_data"] is True
    assert data["forecast"]["has_receivables"] is True
    assert data["forecast"]["has_aging_detail"] is True
    assert data["receivables"] is not None
    assert data["receivables"]["total_open"] > 0
    buckets = {b["bucket"] for b in data["receivables"]["buckets"]}
    assert "0_30" in buckets
    # days_preview содержит receivable_collections
    first_day = data["forecast"]["days_preview"][0]
    assert "receivable_collections" in first_day


async def test_dashboard_reconciliation_after_bank_and_onec(client):
    """После импорта банка и aging ОСВ дашборд возвращает reconciliation."""
    user = await _register(client, company="ReconDashCo")
    headers = auth_headers(user["token"])

    csv_path = f"{FIXTURES_DIR}/sber_sample.csv"
    with open(csv_path, "rb") as f:
        r = await client.post(
            "/imports/bank",
            headers=headers,
            files={"file": ("sber_sample.csv", f, "text/csv")},
            data={"bank_key": "sber"},
        )
    assert r.status_code == 201

    aging_bytes = (ONEC_FIXTURES / "osv_aging_sample.csv").read_bytes()
    r2 = await client.post(
        "/imports/onec",
        headers=headers,
        files={"file": ("osv_aging_sample.csv", aging_bytes, "text/csv")},
    )
    assert r2.status_code == 201

    resp = await client.get("/dashboard/today", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["reconciliation"] is not None
    assert "has_issues" in data["reconciliation"]
    assert "issues" in data["reconciliation"]
    assert isinstance(data["reconciliation"]["issues"], list)


async def test_dashboard_no_reconciliation_bank_only(client):
    """Только банк — reconciliation == null."""
    user = await _register(client, company="BankOnlyReconCo")
    headers = auth_headers(user["token"])

    csv_path = f"{FIXTURES_DIR}/sber_sample.csv"
    with open(csv_path, "rb") as f:
        r = await client.post(
            "/imports/bank",
            headers=headers,
            files={"file": ("sber_sample.csv", f, "text/csv")},
            data={"bank_key": "sber"},
        )
    assert r.status_code == 201

    resp = await client.get("/dashboard/today", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["reconciliation"] is None


async def test_dashboard_plain_onec_no_aging_detail(client):
    """После plain ОСВ has_aging_detail=False, receivables=None (probability=0)."""
    user = await _register(client, company="PlainDashCo")
    headers = auth_headers(user["token"])

    csv_path = f"{FIXTURES_DIR}/sber_sample.csv"
    with open(csv_path, "rb") as f:
        await client.post(
            "/imports/bank",
            headers=headers,
            files={"file": ("sber_sample.csv", f, "text/csv")},
            data={"bank_key": "sber"},
        )

    plain_bytes = (ONEC_FIXTURES / "osv_plain_sample.csv").read_bytes()
    r2 = await client.post(
        "/imports/onec",
        headers=headers,
        files={"file": ("osv_plain_sample.csv", plain_bytes, "text/csv")},
    )
    assert r2.status_code == 201

    resp = await client.get("/dashboard/today", headers=headers)
    data = resp.json()

    assert data["forecast"]["has_aging_detail"] is False
    # Receivables есть в БД (plain), но в прогнозе не участвуют
    # total_open > 0 (записи есть), но без probability
    if data["receivables"] is not None:
        # buckets могут содержать unknown
        buckets = {b["bucket"] for b in data["receivables"]["buckets"]}
        # Если только unknown — aging_detail правильно False
        assert "0_30" not in buckets or data["forecast"]["has_aging_detail"] is True


async def test_dashboard_with_account62_detail(client):
    """После импорта детализации счёта 62 дашборд показывает aging без unknown."""
    user = await _register(client, company="Acct62DashCo")
    headers = auth_headers(user["token"])

    csv_path = f"{FIXTURES_DIR}/sber_sample.csv"
    with open(csv_path, "rb") as f:
        r = await client.post(
            "/imports/bank",
            headers=headers,
            files={"file": ("sber_sample.csv", f, "text/csv")},
            data={"bank_key": "sber"},
        )
    assert r.status_code == 201

    acct62_bytes = (ONEC_FIXTURES / "account62_detail_sample.csv").read_bytes()
    r2 = await client.post(
        "/imports/onec",
        headers=headers,
        files={"file": ("account62_detail_sample.csv", acct62_bytes, "text/csv")},
    )
    assert r2.status_code == 201
    assert r2.json()["meta"]["format"] == "account62_detail"

    resp = await client.get("/dashboard/today", headers=headers)
    data = resp.json()

    assert data["forecast"]["has_receivables"] is True
    assert data["forecast"]["has_aging_detail"] is True
    assert data["receivables"] is not None
    buckets = {b["bucket"] for b in data["receivables"]["buckets"]}
    assert "unknown" not in buckets
    assert len(buckets) >= 2


async def test_dashboard_transactions_after_import(client):
    """После импорта sber GET /dashboard/transactions возвращает список операций."""
    user = await _register(client, company="TxnListCo")
    headers = auth_headers(user["token"])

    csv_path = f"{FIXTURES_DIR}/sber_sample.csv"
    with open(csv_path, "rb") as f:
        r = await client.post(
            "/imports/bank",
            headers=headers,
            files={"file": ("sber_sample.csv", f, "text/csv")},
            data={"bank_key": "sber"},
        )
    assert r.status_code == 201

    resp = await client.get("/dashboard/transactions", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["transactions"]) > 0
    tx = data["transactions"][0]
    assert "date" in tx
    assert "amount" in tx
    assert "direction" in tx
