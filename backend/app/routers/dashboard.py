"""
Router: /dashboard — главный экран.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.rbac import ReadUser
from app.services.report.context import build_report_context

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


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

    return await build_report_context(db, cid, today, obligations_limit=3)


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
