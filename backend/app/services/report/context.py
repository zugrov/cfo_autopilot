"""
Сбор контекста для dashboard и управленческого отчёта.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.explain.engine import explain_balance_change
from app.services.reconciliation.queries import build_reconciliation_payload
from app.services.signals.cash_gap import compute_cash_gap_signal


async def get_company_name(db: AsyncSession, company_id: uuid.UUID) -> str:
    row = await db.execute(
        text("SELECT name FROM company WHERE id = :cid"),
        {"cid": company_id},
    )
    result = row.scalar()
    return result or "Компания"


def _compute_stale(last_import_at: datetime | None) -> tuple[bool, int | None]:
    if not last_import_at:
        return False, None
    now_utc = datetime.now(timezone.utc)
    last_import_aware = (
        last_import_at if last_import_at.tzinfo
        else last_import_at.replace(tzinfo=timezone.utc)
    )
    hours = (now_utc - last_import_aware).total_seconds() / 3600
    is_stale = hours > 24
    return is_stale, int(hours) if is_stale else None


async def build_report_context(
    db: AsyncSession,
    company_id: uuid.UUID,
    as_of: date,
    *,
    obligations_limit: int = 3,
    explain_lookback_days: int = 7,
) -> dict:
    """Единый payload dashboard / PDF / email."""
    cid = company_id

    snap_row = await db.execute(
        text(
            "SELECT balance, forecast_json, computed_at "
            "FROM daily_cash_snapshot "
            "WHERE company_id = :cid AND snapshot_date = :today"
        ),
        {"cid": cid, "today": as_of},
    )
    snap = snap_row.fetchone()

    last_import_row = await db.execute(
        text(
            "SELECT MAX(updated_at) FROM import_batch "
            "WHERE company_id = :cid AND status IN ('done', 'partial')"
        ),
        {"cid": cid},
    )
    last_import_at = last_import_row.scalar()

    obligations_row = await db.execute(
        text(
            "SELECT due_date, amount, description "
            "FROM obligation "
            "WHERE company_id = :cid AND status = 'pending' AND due_date >= :today "
            "ORDER BY due_date LIMIT :limit"
        ),
        {"cid": cid, "today": as_of, "limit": obligations_limit},
    )
    obligations = [
        {
            "due_date": r[0].isoformat(),
            "amount": float(r[1]),
            "description": r[2],
            "days_until": (r[0] - as_of).days,
        }
        for r in obligations_row.fetchall()
    ]

    explain = await explain_balance_change(
        db, cid, as_of, lookback_days=explain_lookback_days
    )
    is_stale, stale_hours = _compute_stale(last_import_at)

    if snap is None:
        return {
            "has_data": False,
            "balance": None,
            "forecast": None,
            "obligations": obligations,
            "explain": None,
            "receivables": None,
            "reconciliation": None,
            "stale": {"is_stale": is_stale, "hours": stale_hours},
            "last_import_at": last_import_at.isoformat() if last_import_at else None,
            "as_of": as_of.isoformat(),
        }

    balance = float(snap[0])
    forecast_json = snap[1]

    gap = compute_cash_gap_signal(forecast_json, as_of)
    deficit_signal = (
        {
            "date": gap.date.isoformat(),
            "is_stress": gap.is_stress,
            "days_until": gap.days_until,
            "severity": gap.severity,
        }
        if gap is not None
        else None
    )

    rcv_buckets_row = await db.execute(
        text(
            "SELECT aging_bucket, SUM(amount) AS total, COUNT(*) AS cnt "
            "FROM receivable "
            "WHERE company_id = :cid AND status IN ('open', 'overdue') "
            "  AND source = 'onec_osv' "
            "GROUP BY aging_bucket"
        ),
        {"cid": cid},
    )
    buckets_raw = rcv_buckets_row.fetchall()

    rcv_top_row = await db.execute(
        text(
            "SELECT c.name, r.amount, r.aging_bucket, r.due_date "
            "FROM receivable r "
            "LEFT JOIN counterparty c ON r.counterparty_id = c.id "
            "WHERE r.company_id = :cid AND r.status IN ('open', 'overdue') "
            "  AND r.source = 'onec_osv' "
            "ORDER BY r.amount DESC LIMIT 5"
        ),
        {"cid": cid},
    )
    top_raw = rcv_top_row.fetchall()

    total_open = sum(float(r[1]) for r in buckets_raw)
    receivables_summary = (
        {
            "total_open": total_open,
            "buckets": [
                {"bucket": r[0], "amount": float(r[1]), "count": int(r[2])}
                for r in buckets_raw
            ],
            "top_counterparties": [
                {
                    "name": r[0] or "—",
                    "amount": float(r[1]),
                    "bucket": r[2],
                    "due_date": r[3].isoformat() if r[3] else None,
                }
                for r in top_raw
            ],
        }
        if buckets_raw
        else None
    )

    reconciliation = await build_reconciliation_payload(
        db, cid, as_of, buckets_raw is not None
    )

    return {
        "has_data": True,
        "balance": balance,
        "forecast": {
            "deficit_day_7": forecast_json.get("deficit_day_7"),
            "deficit_day_14": forecast_json.get("deficit_day_14"),
            "deficit_day_30": forecast_json.get("deficit_day_30"),
            "deficit_day_91": forecast_json.get("deficit_day_91"),
            "deficit_signal": deficit_signal,
            "has_obligations": forecast_json.get("has_obligations", False),
            "has_receivables": forecast_json.get("has_receivables", False),
            "has_aging_detail": forecast_json.get("has_aging_detail", False),
            "days_preview": [
                {
                    "date": d["date"],
                    "balance": d["balance"],
                    "receivable_collections": d.get("receivable_collections", 0),
                }
                for d in forecast_json.get("days", [])
            ],
            "days_stress": forecast_json.get("days_stress", []),
        },
        "obligations": obligations,
        "explain": {
            "headline": explain.headline,
            "reasons": [
                {
                    "type": r.type,
                    "label": r.label,
                    "amount": r.amount,
                    "date": r.date,
                }
                for r in explain.reasons
            ],
        },
        "receivables": receivables_summary,
        "reconciliation": reconciliation,
        "stale": {"is_stale": is_stale, "hours": stale_hours},
        "last_import_at": last_import_at.isoformat() if last_import_at else None,
        "as_of": as_of.isoformat(),
    }
