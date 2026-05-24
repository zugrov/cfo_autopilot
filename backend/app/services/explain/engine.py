"""
ExplainEngine — rule-based объяснение изменения остатка.

Sprint 2: C2 top-3 typed drivers — списание / поступление / обязательства на 7 дней.
Sprint 3: LLM-enhanced explanations.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


@dataclass
class ExplainReason:
    type: str      # "debit" | "credit" | "obligations"
    label: str     # «Аренда офиса» / «ООО Клиент» / «Зарплата, аренда»
    amount: float
    date: str | None = None  # ISO-дата транзакции; None для обязательств


@dataclass
class ExplainResult:
    headline: str                    # «Остаток снизился на ₽120 000 за 7 дней»
    reasons: list[ExplainReason] = field(default_factory=list)
    # устаревшие поля — оставлены для обратной совместимости до обновления dashboard
    top_reason: str = ""
    detail_rows: list[dict] = field(default_factory=list)


async def explain_balance_change(
    db: AsyncSession,
    company_id: uuid.UUID,
    as_of: date,
    lookback_days: int = 7,
) -> ExplainResult:
    """
    Находит до 3 ключевых драйверов изменения остатка за последние N дней.

    Типы (C2):
      1. debit — крупнейшее списание за период
      2. credit — крупнейшее поступление за период
      3. obligations — сумма ближайших обязательств (горизонт = lookback_days)

    Пустой тип — не добавляем (D1).
    """
    since = as_of - timedelta(days=lookback_days)

    rows = await db.execute(
        text(
            "SELECT txn_date, amount, direction, counterparty_raw, purpose "
            "FROM transaction "
            "WHERE company_id = :cid AND txn_date BETWEEN :since AND :until "
            "ORDER BY amount DESC "
            "LIMIT 50"
        ),
        {"cid": company_id, "since": since, "until": as_of},
    )
    txns = rows.fetchall()

    if not txns:
        return ExplainResult(
            headline="Нет транзакций за последние 7 дней",
            top_reason="Загрузите банковскую выписку для анализа",
        )

    total_credit = sum(Decimal(str(r[1])) for r in txns if r[2] == "credit")
    total_debit = sum(Decimal(str(r[1])) for r in txns if r[2] == "debit")
    net_change = total_credit - total_debit

    sign = "вырос" if net_change >= 0 else "снизился"
    headline = f"Остаток {sign} на ₽{abs(net_change):,.0f} за {lookback_days} дней".replace(",", " ")

    reasons: list[ExplainReason] = []

    # Driver 1 — крупнейшее списание
    debits = [r for r in txns if r[2] == "debit"]
    if debits:
        top_d = max(debits, key=lambda r: r[1])
        label = _txn_label(top_d)
        reasons.append(ExplainReason(
            type="debit",
            label=f"Списание: {label}",
            amount=float(top_d[1]),
            date=top_d[0].isoformat(),
        ))

    # Driver 2 — крупнейшее поступление
    credits = [r for r in txns if r[2] == "credit"]
    if credits:
        top_c = max(credits, key=lambda r: r[1])
        label = _txn_label(top_c)
        reasons.append(ExplainReason(
            type="credit",
            label=f"Поступление: {label}",
            amount=float(top_c[1]),
            date=top_c[0].isoformat(),
        ))

    # Driver 3 — обязательства на горизонт lookback_days вперёд
    ob_until = as_of + timedelta(days=lookback_days)
    ob_rows = await db.execute(
        text(
            "SELECT amount, description FROM obligation "
            "WHERE company_id = :cid AND status = 'pending' "
            "AND due_date BETWEEN :today AND :until "
            "ORDER BY due_date LIMIT 10"
        ),
        {"cid": company_id, "today": as_of, "until": ob_until},
    )
    obligations = ob_rows.fetchall()
    if obligations:
        total_ob = sum(float(r[0]) for r in obligations)
        labels = ", ".join(r[1] for r in obligations[:3] if r[1])
        reasons.append(ExplainReason(
            type="obligations",
            label=f"Обязательства: {labels}" if labels else "Обязательства на 7 дней",
            amount=total_ob,
            date=None,
        ))

    # top_reason для обратной совместимости — первый из drivers
    top_reason = reasons[0].label if reasons else ""

    detail_rows = [
        {
            "date": r[0].isoformat(),
            "amount": float(r[1]),
            "direction": r[2],
            "counterparty": r[3],
            "purpose": r[4],
        }
        for r in txns[:10]
    ]

    return ExplainResult(
        headline=headline,
        reasons=reasons,
        top_reason=top_reason,
        detail_rows=detail_rows,
    )


def _txn_label(row: tuple) -> str:
    counterparty = row[3] or ""
    purpose = row[4] or ""
    parts = [p for p in [counterparty, purpose] if p]
    label = ": ".join(parts) if parts else "контрагент не указан"
    # обрезаем до 60 символов
    return label[:60] + ("…" if len(label) > 60 else "")
