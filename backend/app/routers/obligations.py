"""
Router: /obligations — платёжный календарь.
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import CurrentUser
from app.core.audit import log_action

router = APIRouter(prefix="/obligations", tags=["obligations"])


class ObligationCreate(BaseModel):
    due_date: date
    amount: float
    description: str
    is_recurring: bool = False


class ObligationResponse(BaseModel):
    id: uuid.UUID
    due_date: date
    amount: float
    description: str
    status: str
    is_recurring: bool


@router.get("", summary="Список обязательств")
async def list_obligations(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    cid = current_user.company_id
    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"),
        {"cid": str(cid)},
    )
    result = await db.execute(
        text(
            "SELECT id, due_date, amount, description, status, is_recurring "
            "FROM obligation WHERE company_id = :cid "
            "ORDER BY due_date"
        ),
        {"cid": cid},
    )
    rows = result.fetchall()
    return {
        "obligations": [
            {
                "id": str(r[0]),
                "due_date": r[1].isoformat(),
                "amount": float(r[2]),
                "description": r[3],
                "status": r[4],
                "is_recurring": r[5],
            }
            for r in rows
        ]
    }


@router.post("", status_code=status.HTTP_201_CREATED, summary="Создать обязательство")
async def create_obligation(
    body: ObligationCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    cid = current_user.company_id
    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"),
        {"cid": str(cid)},
    )

    new_id = uuid.uuid4()
    await db.execute(
        text(
            "INSERT INTO obligation (id, company_id, due_date, amount, description, status, is_recurring, created_at) "
            "VALUES (:id, :cid, :due_date, :amount, :description, 'pending', :is_recurring, now())"
        ),
        {
            "id": new_id,
            "cid": cid,
            "due_date": body.due_date,
            "amount": body.amount,
            "description": body.description,
            "is_recurring": body.is_recurring,
        },
    )
    await log_action(
        db, company_id=cid, user_id=current_user.id,
        action="create_obligation", entity="obligation", entity_id=new_id,
    )
    await db.commit()

    # Триггерим пересчёт прогноза
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        from app.core.config import get_settings
        settings = get_settings()
        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await redis.enqueue_job("task_recompute_snapshot", str(cid))
        await redis.aclose()
    except Exception:
        pass

    return {"id": str(new_id), "status": "created"}


@router.patch("/{obligation_id}/pay", summary="Отметить обязательство как оплаченное")
async def mark_paid(
    obligation_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    cid = current_user.company_id
    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"),
        {"cid": str(cid)},
    )
    await db.execute(
        text(
            "UPDATE obligation SET status = 'paid' "
            "WHERE id = :id AND company_id = :cid"
        ),
        {"id": obligation_id, "cid": cid},
    )
    await log_action(
        db, company_id=cid, user_id=current_user.id,
        action="mark_obligation_paid", entity="obligation", entity_id=obligation_id,
    )
    await db.commit()
    return {"status": "paid"}
