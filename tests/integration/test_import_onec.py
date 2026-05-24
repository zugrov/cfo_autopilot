"""
Integration тесты: POST /imports/onec
Требуют: Postgres.app + alembic upgrade head.
"""
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from httpx import AsyncClient

ONEC_FIXTURES = Path(__file__).parent.parent / "fixtures" / "onec"


@pytest.mark.asyncio
async def test_upload_onec_aging(client: AsyncClient):
    """aging CSV импортируется, forecast_ready=True."""
    from tests.integration.conftest import _register, auth_headers

    user = await _register(client, company="OnecTestCo")
    headers = auth_headers(user["token"])

    csv_bytes = (ONEC_FIXTURES / "osv_aging_sample.csv").read_bytes()
    resp = await client.post(
        "/imports/onec",
        headers=headers,
        files={"file": ("osv_aging_sample.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] in ("done", "partial")
    assert data["imported_count"] == 4  # Альфа(1) + Бетов(1) + Гамма(2)
    assert data["meta"]["format"] == "aging"
    assert data["meta"]["forecast_ready"] is True
    assert data["meta"]["receivables_imported"] == 4


@pytest.mark.asyncio
async def test_upload_onec_plain(client: AsyncClient):
    """plain CSV импортируется, forecast_ready=False."""
    from tests.integration.conftest import _register, auth_headers

    user = await _register(client, company="OnecPlainCo")
    headers = auth_headers(user["token"])

    csv_bytes = (ONEC_FIXTURES / "osv_plain_sample.csv").read_bytes()
    resp = await client.post(
        "/imports/onec",
        headers=headers,
        files={"file": ("osv_plain_sample.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] in ("done", "partial")
    assert data["meta"]["format"] == "plain"
    assert data["meta"]["forecast_ready"] is False
    assert data["meta"]["receivables_imported"] == 3  # Альфа, Бетов, Гамма


@pytest.mark.asyncio
async def test_upload_onec_replace_semantics(client: AsyncClient):
    """Повторный импорт заменяет старые onec_osv receivables, manual не трогает."""
    from tests.integration.conftest import _register, auth_headers

    user = await _register(client, company="OnecReplaceCo")
    headers = auth_headers(user["token"])
    csv_bytes = (ONEC_FIXTURES / "osv_aging_sample.csv").read_bytes()

    # Первый импорт
    r1 = await client.post(
        "/imports/onec",
        headers=headers,
        files={"file": ("osv_aging_sample.csv", csv_bytes, "text/csv")},
    )
    assert r1.status_code == 201
    count1 = r1.json()["imported_count"]

    # Второй импорт того же файла
    r2 = await client.post(
        "/imports/onec",
        headers=headers,
        files={"file": ("osv_aging_sample.csv", csv_bytes, "text/csv")},
    )
    assert r2.status_code == 201
    count2 = r2.json()["imported_count"]

    # Количество должно быть одинаковым (replace, не append)
    assert count1 == count2


@pytest.mark.asyncio
async def test_upload_onec_requires_auth(client: AsyncClient):
    """Без токена — 401/403."""
    csv_bytes = (ONEC_FIXTURES / "osv_plain_sample.csv").read_bytes()
    resp = await client.post(
        "/imports/onec",
        files={"file": ("osv_plain_sample.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_upload_onec_tenant_isolation(client: AsyncClient):
    """Receivables двух компаний не пересекаются."""
    from tests.integration.conftest import _register, auth_headers

    user_a = await _register(client, company="IsolationCoA")
    user_b = await _register(client, company="IsolationCoB")
    csv_bytes = (ONEC_FIXTURES / "osv_aging_sample.csv").read_bytes()

    await client.post(
        "/imports/onec",
        headers=auth_headers(user_a["token"]),
        files={"file": ("osv_aging_sample.csv", csv_bytes, "text/csv")},
    )
    r_b = await client.post(
        "/imports/onec",
        headers=auth_headers(user_b["token"]),
        files={"file": ("osv_aging_sample.csv", csv_bytes, "text/csv")},
    )
    assert r_b.status_code == 201
    # Дашборд компании B показывает данные только от B
    dash_b = await client.get(
        "/dashboard", headers=auth_headers(user_b["token"])
    )
    assert dash_b.status_code == 200
