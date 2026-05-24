"""
ExplainEngine — минимальное rule-based объяснение изменения остатка.

Sprint 1: топ-1 причина изменения за 7 дней.
Sprint 3: LLM-enhanced explanations.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


@dataclass
class ExplainResult:
    headline: str           # «Остаток снизился на ₽120 000 за 7 дней»
    top_reason: str         # «Крупнейшее списание: Аренда офиса (₽80 000, 20.01)»
    detail_rows: list[dict]  # [{date, amount, direction, counterparty, purpose}]


async def explain_balance_change(
    db: AsyncSession,
    company_id: uuid.UUID,
    as_of: date,
    lookback_days: int = 7,
) -> ExplainResult:
    """Находит топ-1 причину изменения остатка за последние N дней."""
    since = as_of - timedelta(days=lookback_days)

    rows = await db.execute(
        text(
            "SELECT txn_date, amount, direction, counterparty_raw, purpose "
            "FROM transaction "
            "WHERE company_id = :cid AND txn_date BETWEEN :since AND :until "
            "ORDER BY amount DESC "
            "LIMIT 10"
        ),
        {"cid": company_id, "since": since, "until": as_of},
    )
    txns = rows.fetchall()

    if not txns:
        return ExplainResult(
            headline="Нет транзакций за последние 7 дней",
            top_reason="Загрузите банковскую выписку для анализа",
            detail_rows=[],
        )

    total_credit = sum(Decimal(str(r[1])) for r in txns if r[2] == "credit")
    total_debit = sum(Decimal(str(r[1])) for r in txns if r[2] == "debit")
    net_change = total_credit - total_debit

    sign = "вырос" if net_change >= 0 else "снизился"
    headline = f"Остаток {sign} на ₽{abs(net_change):,.0f} за {lookback_days} дней".replace(",", " ")

    top = max(txns, key=lambda r: r[1])
    top_direction = "списание" if top[2] == "debit" else "поступление"
    top_counterparty = top[3] or "контрагент не указан"
    top_purpose = top[4] or ""
    top_label = f"{top_counterparty}: {top_purpose}".strip(": ")
    top_reason = (
        f"Крупнейшее {top_direction}: {top_label} "
        f"(₽{Decimal(str(top[1])):,.0f}, {top[0].strftime('%d.%m')})".replace(",", " ")
    )

    detail_rows = [
        {
            "date": r[0].isoformat(),
            "amount": float(r[1]),
            "direction": r[2],
            "counterparty": r[3],
            "purpose": r[4],
        }
        for r in txns
    ]

    return ExplainResult(headline=headline, top_reason=top_reason, detail_rows=detail_rows)
