"""
Deduper — вычисляет dedupe_hash для транзакций.

Hash строится по: company_id + txn_date + amount + direction + counterparty[:64] + purpose[:64]
ИНН в хеш НЕ включается — он отсутствует в большинстве банковских выписок.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import date
from decimal import Decimal


def compute_dedupe_hash(
    company_id: uuid.UUID,
    txn_date: date,
    amount: Decimal,
    direction: str,
    counterparty_raw: str | None,
    purpose: str | None,
) -> str:
    """
    Возвращает SHA256 hex-дайджест (64 символа).
    Детерминирован: одни и те же входные данные → одинаковый хеш.
    """
    parts = [
        str(company_id),
        txn_date.isoformat(),
        str(amount),
        direction,
        (counterparty_raw or "")[:64],
        (purpose or "")[:64],
    ]
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
