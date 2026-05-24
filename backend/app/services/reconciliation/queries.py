"""
SQL-запросы для блока сверки на dashboard и в отчётах.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.reconciliation.engine import compute_reconciliation

RECON_LOOKBACK_DAYS = 90


async def build_reconciliation_payload(
    db: AsyncSession,
    company_id: uuid.UUID,
    as_of: date,
    has_onec_receivables: bool,
) -> dict | None:
    """Сверка банк vs 1С — только если подключены оба источника."""
    if not has_onec_receivables:
        return None

    since = as_of - timedelta(days=RECON_LOOKBACK_DAYS)
    bank_row = await db.execute(
        text(
            "SELECT counterparty_raw, amount, txn_date "
            "FROM transaction "
            "WHERE company_id = :cid AND direction = 'credit' "
            "  AND txn_date >= :since"
        ),
        {"cid": company_id, "since": since},
    )
    bank_raw = bank_row.fetchall()
    if not bank_raw:
        return None

    rcv_row = await db.execute(
        text(
            "SELECT c.name, r.amount, r.due_date, r.status "
            "FROM receivable r "
            "LEFT JOIN counterparty c ON r.counterparty_id = c.id "
            "WHERE r.company_id = :cid AND r.status IN ('open', 'overdue') "
            "  AND r.source = 'onec_osv'"
        ),
        {"cid": company_id},
    )
    rcv_raw = rcv_row.fetchall()
    if not rcv_raw:
        return None

    bank_credits = [
        {
            "counterparty": r[0] or "",
            "amount": float(r[1]),
            "txn_date": r[2],
        }
        for r in bank_raw
    ]
    receivables = [
        {
            "counterparty": r[0] or "",
            "amount": float(r[1]),
            "due_date": r[2],
            "status": r[3],
        }
        for r in rcv_raw
    ]

    issues = compute_reconciliation(
        receivables,
        bank_credits,
        as_of,
        lookback_days=RECON_LOOKBACK_DAYS,
    )
    return {
        "has_issues": len(issues) > 0,
        "issues": [
            {
                "kind": i.kind,
                "counterparty": i.counterparty,
                "amount": i.amount,
                "detail": i.detail,
            }
            for i in issues
        ],
    }
