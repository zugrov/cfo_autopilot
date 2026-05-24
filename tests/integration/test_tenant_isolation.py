"""
Тест tenant isolation: данные компании A не видны компании B через RLS.
"""
import pytest
import pytest_asyncio

from .conftest import _register, auth_headers, FIXTURES_DIR


pytestmark = pytest.mark.asyncio


async def test_tenant_isolation(client):
    """
    Компания A загружает выписку.
    Компания B не должна видеть транзакции компании A в дашборде.
    """
    user_a = await _register(client, company="Company A")
    user_b = await _register(client, company="Company B")

    csv_path = f"{FIXTURES_DIR}/sber_sample.csv"
    with open(csv_path, "rb") as f:
        resp = await client.post(
            "/imports/bank",
            headers=auth_headers(user_a["token"]),
            files={"file": ("sber_sample.csv", f, "text/csv")},
            data={"bank_key": "sber"},
        )
    assert resp.status_code == 201, resp.text
    batch = resp.json()
    assert batch["imported_count"] > 0

    # Компания B не видит данные — has_data=false (нет snapshot)
    resp_b = await client.get(
        "/dashboard/today",
        headers=auth_headers(user_b["token"]),
    )
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert data_b["has_data"] is False, "Компания B видит данные компании A — нарушение tenant isolation"

    # Компания A видит свой last_import_at
    resp_a = await client.get(
        "/dashboard/today",
        headers=auth_headers(user_a["token"]),
    )
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert data_a["last_import_at"] is not None, "Компания A не видит свой импорт"
