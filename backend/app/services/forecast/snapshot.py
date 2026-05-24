"""
SnapshotService — сохраняет/обновляет daily_cash_snapshot в БД.
Вызывается из ARQ worker после каждого импорта.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models import DailyCashSnapshot, Transaction, Obligation
from app.services.forecast.engine import compute_forecast, ForecastResult


async def _get_current_balance(db: AsyncSession, company_id: uuid.UUID) -> Decimal:
    """Последний известный остаток = сумма всех credit - debit транзакций."""
    result = await db.execute(
        text(
            "SELECT "
            "  SUM(CASE WHEN direction='credit' THEN amount ELSE 0 END) - "
            "  SUM(CASE WHEN direction='debit' THEN amount ELSE 0 END) "
            "FROM transaction WHERE company_id = :cid"
        ),
        {"cid": company_id},
    )
    balance = result.scalar()
    return Decimal(str(balance or 0))


async def recompute_snapshot(
    db: AsyncSession,
    company_id: uuid.UUID,
    as_of: date | None = None,
) -> DailyCashSnapshot:
    """
    Пересчитывает снапшот для company_id на указанную дату (default: сегодня).
    Upsert: если запись уже существует — обновляет.
    """
    if as_of is None:
        as_of = date.today()

    # Транзакции за последние 30 дней для расчёта медианы
    txn_rows = await db.execute(
        text(
            "SELECT txn_date, amount, direction FROM transaction "
            "WHERE company_id = :cid AND txn_date >= :since "
            "ORDER BY txn_date"
        ),
        {"cid": company_id, "since": as_of.replace(month=max(1, as_of.month - 1))},
    )
    transactions = [
        {"txn_date": r[0], "amount": Decimal(str(r[1])), "direction": r[2]}
        for r in txn_rows.fetchall()
    ]

    # Обязательства
    ob_rows = await db.execute(
        text(
            "SELECT due_date, amount, status FROM obligation "
            "WHERE company_id = :cid AND status = 'pending'"
        ),
        {"cid": company_id},
    )
    obligations = [
        {"due_date": r[0], "amount": Decimal(str(r[1])), "status": r[2]}
        for r in ob_rows.fetchall()
    ]

    # Дебиторка (только open/overdue с collection_probability > 0)
    rcv_rows = await db.execute(
        text(
            "SELECT due_date, amount, collection_probability, aging_bucket, status "
            "FROM receivable "
            "WHERE company_id = :cid AND status IN ('open', 'overdue') "
            "AND collection_probability IS NOT NULL AND collection_probability > 0"
        ),
        {"cid": company_id},
    )
    receivables = [
        {
            "due_date": r[0],
            "expected_amount": Decimal(str(r[1])) * Decimal(str(r[2])),
            "aging_bucket": r[3],
            "status": r[4],
        }
        for r in rcv_rows.fetchall()
    ]

    current_balance = await _get_current_balance(db, company_id)

    common_args = dict(
        company_id=company_id,
        current_balance=current_balance,
        transactions=transactions,
        obligations=obligations,
        receivables=receivables,
        as_of_date=as_of,
        horizon_days=91,
    )

    forecast = compute_forecast(**common_args, scenario="base")
    forecast_stress = compute_forecast(**common_args, scenario="stress")

    forecast_json = {
        "days": [
            {
                "date": d.day.isoformat(),
                "balance": float(d.forecast_balance),
                "inflow": float(d.inflow_estimate),
                "outflow": float(d.outflow_obligations),
                "receivable_collections": float(d.receivable_collections),
            }
            for d in forecast.days
        ],
        "days_stress": [
            {
                "date": d.day.isoformat(),
                "balance": float(d.forecast_balance),
            }
            for d in forecast_stress.days
        ],
        "deficit_day_7": forecast.deficit_day_7.isoformat() if forecast.deficit_day_7 else None,
        "deficit_day_14": forecast.deficit_day_14.isoformat() if forecast.deficit_day_14 else None,
        "deficit_day_30": forecast.deficit_day_30.isoformat() if forecast.deficit_day_30 else None,
        "deficit_day_91": forecast.deficit_day_91.isoformat() if forecast.deficit_day_91 else None,
        "deficit_day_7_stress": forecast_stress.deficit_day_7.isoformat() if forecast_stress.deficit_day_7 else None,
        "deficit_day_14_stress": forecast_stress.deficit_day_14.isoformat() if forecast_stress.deficit_day_14 else None,
        "deficit_day_30_stress": forecast_stress.deficit_day_30.isoformat() if forecast_stress.deficit_day_30 else None,
        "deficit_day_91_stress": forecast_stress.deficit_day_91.isoformat() if forecast_stress.deficit_day_91 else None,
        "has_obligations": forecast.has_obligations,
        "has_receivables": forecast.has_receivables,
        "has_aging_detail": forecast.has_aging_detail,
    }

    await db.execute(
        text(
            "INSERT INTO daily_cash_snapshot (company_id, snapshot_date, balance, forecast_json, computed_at) "
            "VALUES (:cid, :snap_date, :balance, CAST(:forecast_json AS jsonb), now()) "
            "ON CONFLICT (company_id, snapshot_date) DO UPDATE SET "
            "  balance = EXCLUDED.balance, "
            "  forecast_json = EXCLUDED.forecast_json, "
            "  computed_at = now()"
        ),
        {
            "cid": company_id,
            "snap_date": as_of,
            "balance": float(current_balance),
            "forecast_json": __import__("json").dumps(forecast_json),
        },
    )

    result = await db.execute(
        text(
            "SELECT company_id, snapshot_date, balance, forecast_json, computed_at "
            "FROM daily_cash_snapshot WHERE company_id = :cid AND snapshot_date = :snap_date"
        ),
        {"cid": company_id, "snap_date": as_of},
    )
    row = result.fetchone()
    snap = DailyCashSnapshot()
    snap.company_id = row[0]
    snap.snapshot_date = row[1]
    snap.balance = Decimal(str(row[2]))
    snap.forecast_json = row[3]
    snap.computed_at = row[4]
    return snap
