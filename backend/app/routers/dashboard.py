"""
Router: /dashboard — главный экран.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.rbac import ReadUser
from app.services.explain.engine import explain_balance_change
from app.services.signals.cash_gap import compute_cash_gap_signal
from app.services.reconciliation.engine import compute_reconciliation

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_RECON_LOOKBACK_DAYS = 90


@router.get("/today", summary="Главный экран: остаток + прогноз + сигналы")
async def dashboard_today(
    current_user: ReadUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    cid = current_user.company_id
    today = date.today()

    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"),
        {"cid": str(cid)},
    )

    # Снапшот
    snap_row = await db.execute(
        text(
            "SELECT balance, forecast_json, computed_at "
            "FROM daily_cash_snapshot "
            "WHERE company_id = :cid AND snapshot_date = :today"
        ),
        {"cid": cid, "today": today},
    )
    snap = snap_row.fetchone()

    # Дата последнего импорта
    last_import_row = await db.execute(
        text(
            "SELECT MAX(updated_at) FROM import_batch "
            "WHERE company_id = :cid AND status IN ('done', 'partial')"
        ),
        {"cid": cid},
    )
    last_import_at = last_import_row.scalar()

    # Ближайшие 3 обязательства
    obligations_row = await db.execute(
        text(
            "SELECT due_date, amount, description "
            "FROM obligation "
            "WHERE company_id = :cid AND status = 'pending' AND due_date >= :today "
            "ORDER BY due_date LIMIT 3"
        ),
        {"cid": cid, "today": today},
    )
    obligations = [
        {
            "due_date": r[0].isoformat(),
            "amount": float(r[1]),
            "description": r[2],
            "days_until": (r[0] - today).days,
        }
        for r in obligations_row.fetchall()
    ]

    # Объяснение
    explain = await explain_balance_change(db, cid, today)

    # Stale data flag — считается inline, не персистируется
    is_stale = False
    stale_hours = None
    if last_import_at:
        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc)
        last_import_aware = (
            last_import_at if last_import_at.tzinfo
            else last_import_at.replace(tzinfo=timezone.utc)
        )
        hours = (now_utc - last_import_aware).total_seconds() / 3600
        is_stale = hours > 24
        stale_hours = int(hours) if is_stale else None

    if snap is None:
        return {
            "has_data": False,
            "balance": None,
            "forecast": None,
            "obligations": obligations,
            "explain": None,
            "reconciliation": None,
            "stale": {"is_stale": is_stale, "hours": stale_hours},
            "last_import_at": last_import_at.isoformat() if last_import_at else None,
        }

    balance = float(snap[0])
    forecast_json = snap[1]

    # Сигнал кассового разрыва — единый B3 с severity
    gap = compute_cash_gap_signal(forecast_json, today)
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

    # Сводка дебиторки по aging-корзинам
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

    reconciliation = await _build_reconciliation(
        db, cid, today, buckets_raw is not None
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
    }


async def _build_reconciliation(
    db: AsyncSession,
    cid: uuid.UUID,
    today: date,
    has_onec_receivables: bool,
) -> dict | None:
    """Сверка банк vs 1С — только если подключены оба источника."""
    if not has_onec_receivables:
        return None

    since = today - timedelta(days=_RECON_LOOKBACK_DAYS)
    bank_row = await db.execute(
        text(
            "SELECT counterparty_raw, amount, txn_date "
            "FROM transaction "
            "WHERE company_id = :cid AND direction = 'credit' "
            "  AND txn_date >= :since"
        ),
        {"cid": cid, "since": since},
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
        {"cid": cid},
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
        today,
        lookback_days=_RECON_LOOKBACK_DAYS,
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


@router.get("/transactions", summary="Список транзакций")
async def list_transactions(
    current_user: ReadUser,
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
) -> dict:
    cid = current_user.company_id
    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"),
        {"cid": str(cid)},
    )
    result = await db.execute(
        text(
            "SELECT txn_date, amount, direction, counterparty_raw, purpose "
            "FROM transaction "
            "WHERE company_id = :cid "
            "ORDER BY txn_date DESC, created_at DESC "
            "LIMIT :limit OFFSET :offset"
        ),
        {"cid": cid, "limit": limit, "offset": offset},
    )
    rows = result.fetchall()
    return {
        "transactions": [
            {
                "date": r[0].isoformat(),
                "amount": float(r[1]),
                "direction": r[2],
                "counterparty": r[3],
                "purpose": r[4],
            }
            for r in rows
        ]
    }
