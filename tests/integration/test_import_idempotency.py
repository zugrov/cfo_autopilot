"""
Тест idempotent import: повторная загрузка того же CSV не дублирует транзакции.
"""
import pytest

from .conftest import _register, auth_headers, FIXTURES_DIR


pytestmark = pytest.mark.asyncio


async def test_import_idempotency(client):
    """Загружаем один CSV дважды — количество транзакций не меняется."""
    user = await _register(client, company="Idempotency Test Co")
    csv_path = f"{FIXTURES_DIR}/sber_sample.csv"

    # Первая загрузка
    with open(csv_path, "rb") as f:
        resp1 = await client.post(
            "/imports/bank",
            headers=auth_headers(user["token"]),
            files={"file": ("sber_sample.csv", f, "text/csv")},
            data={"bank_key": "sber"},
        )
    assert resp1.status_code == 201, resp1.text
    batch1 = resp1.json()
    imported1 = batch1["imported_count"]
    assert imported1 > 0

    # Вторая загрузка того же файла
    with open(csv_path, "rb") as f:
        resp2 = await client.post(
            "/imports/bank",
            headers=auth_headers(user["token"]),
            files={"file": ("sber_sample.csv", f, "text/csv")},
            data={"bank_key": "sber"},
        )
    assert resp2.status_code == 201, resp2.text
    batch2 = resp2.json()

    # Дубликаты пропускаются — imported_count = 0 при повторной загрузке
    assert batch2["imported_count"] == 0, (
        f"Дублирование транзакций: первая загрузка {imported1}, вторая {batch2['imported_count']}"
    )
