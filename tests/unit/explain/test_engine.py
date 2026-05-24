"""
Unit-тесты: ExplainEngine Sprint 2 (C2 top-3 typed drivers).
"""
import uuid
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.services.explain.engine import explain_balance_change, ExplainReason


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def scalar(self):
        return self._rows[0] if self._rows else None


def _make_db(txn_rows, ob_rows=None):
    """Создаёт mock DB, возвращающий заданные строки."""
    db = AsyncMock()
    call_count = 0

    async def execute(query, params=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return FakeCursor(txn_rows)
        return FakeCursor(ob_rows or [])

    db.execute.side_effect = execute
    return db


@pytest.mark.asyncio
async def test_no_transactions_returns_empty():
    db = _make_db([])
    result = await explain_balance_change(db, uuid.uuid4(), date.today())
    assert "нет транзакций" in result.headline.lower()
    assert result.reasons == []


@pytest.mark.asyncio
async def test_debit_driver_present():
    txn_rows = [
        (date.today(), 80000, "debit", "Аренда офиса", "Офис Арбат"),
        (date.today(), 30000, "credit", "ООО Клиент", "Оплата счёта"),
    ]
    db = _make_db(txn_rows)
    result = await explain_balance_change(db, uuid.uuid4(), date.today())
    types = [r.type for r in result.reasons]
    assert "debit" in types


@pytest.mark.asyncio
async def test_credit_driver_present():
    txn_rows = [
        (date.today(), 80000, "debit", "Аренда", ""),
        (date.today(), 120000, "credit", "ООО Клиент", "Аванс"),
    ]
    db = _make_db(txn_rows)
    result = await explain_balance_change(db, uuid.uuid4(), date.today())
    types = [r.type for r in result.reasons]
    assert "credit" in types


@pytest.mark.asyncio
async def test_obligations_driver_present():
    txn_rows = [
        (date.today(), 50000, "debit", "НДС", ""),
    ]
    ob_rows = [
        (150000, "Зарплата"),
        (80000, "Аренда"),
    ]
    db = _make_db(txn_rows, ob_rows)
    result = await explain_balance_change(db, uuid.uuid4(), date.today())
    types = [r.type for r in result.reasons]
    assert "obligations" in types
    ob_reason = next(r for r in result.reasons if r.type == "obligations")
    assert ob_reason.amount == 230000


@pytest.mark.asyncio
async def test_empty_type_not_added_debit_only():
    """Только дебет — нет кредита в транзакциях — кредит-driver не появляется."""
    txn_rows = [
        (date.today(), 50000, "debit", "Поставщик", ""),
    ]
    db = _make_db(txn_rows, [])
    result = await explain_balance_change(db, uuid.uuid4(), date.today())
    types = [r.type for r in result.reasons]
    assert "credit" not in types
    assert "debit" in types


@pytest.mark.asyncio
async def test_at_most_three_reasons():
    txn_rows = [
        (date.today(), 80000, "debit", "Аренда", ""),
        (date.today(), 30000, "credit", "ООО Клиент", ""),
    ]
    ob_rows = [(100000, "Зарплата")]
    db = _make_db(txn_rows, ob_rows)
    result = await explain_balance_change(db, uuid.uuid4(), date.today())
    assert len(result.reasons) <= 3


@pytest.mark.asyncio
async def test_reason_amounts_positive():
    txn_rows = [
        (date.today(), 80000, "debit", "Аренда", ""),
        (date.today(), 30000, "credit", "Клиент", ""),
    ]
    db = _make_db(txn_rows)
    result = await explain_balance_change(db, uuid.uuid4(), date.today())
    for r in result.reasons:
        assert r.amount > 0, f"Amount должен быть > 0: {r}"


@pytest.mark.asyncio
async def test_headline_contains_direction():
    txn_rows = [(date.today(), 50000, "debit", "Аренда", "")]
    db = _make_db(txn_rows)
    result = await explain_balance_change(db, uuid.uuid4(), date.today())
    assert "снизился" in result.headline or "вырос" in result.headline
