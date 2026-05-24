"""
Router: /dashboard — главный экран.
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.auth import CurrentUser
from app.services.explain.engine import explain_balance_change

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/today", summary="Главный экран: остаток + прогноз + сигналы")
async def dashboard_today(
    current_user: CurrentUser,
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

    # Активные алерты
    alerts_row = await db.execute(
        text(
            "SELECT alert_type, payload FROM alert "
            "WHERE company_id = :cid AND sent_at IS NULL "
            "ORDER BY created_at DESC LIMIT 5"
        ),
        {"cid": cid},
    )
    alerts = [{"type": r[0], "payload": r[1]} for r in alerts_row.fetchall()]

    # Объяснение
    explain = await explain_balance_change(db, cid, today)

    # Stale data flag
    is_stale = False
    stale_hours = None
    if last_import_at:
        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc)
        last_import_aware = last_import_at if last_import_at.tzinfo else last_import_at.replace(tzinfo=timezone.utc)
        hours = (now_utc - last_import_aware).total_seconds() / 3600
        is_stale = hours > 24
        stale_hours = int(hours) if is_stale else None

    if snap is None:
        return {
            "has_data": False,
            "balance": None,
            "forecast": None,
            "obligations": obligations,
            "alerts": alerts,
            "explain": None,
            "stale": {"is_stale": is_stale, "hours": stale_hours},
            "last_import_at": last_import_at.isoformat() if last_import_at else None,
        }

    balance = float(snap[0])
    forecast_json = snap[1]

    return {
        "has_data": True,
        "balance": balance,
        "forecast": {
            "deficit_day_7": forecast_json.get("deficit_day_7"),
            "deficit_day_14": forecast_json.get("deficit_day_14"),
            "deficit_day_30": forecast_json.get("deficit_day_30"),
            "deficit_day_91": forecast_json.get("deficit_day_91"),
            "has_obligations": forecast_json.get("has_obligations", False),
            "days_preview": forecast_json.get("days", [])[:30],
        },
        "obligations": obligations,
        "alerts": alerts,
        "explain": {
            "headline": explain.headline,
            "top_reason": explain.top_reason,
        },
        "stale": {"is_stale": is_stale, "hours": stale_hours},
        "last_import_at": last_import_at.isoformat() if last_import_at else None,
    }


@router.get("/transactions", summary="Список транзакций")
async def list_transactions(
    current_user: CurrentUser,
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
