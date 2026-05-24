"""
ARQ Workers — фоновые задачи.

Задачи:
- recompute_snapshot: пересчёт daily_cash_snapshot после импорта
- send_telegram_digest: отправка ежедневного дайджеста в 08:00 MSK

Запуск: arq app.workers.settings.WorkerSettings
"""
from __future__ import annotations

import uuid
from datetime import date

from arq import ArqRedis
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.services.forecast.snapshot import recompute_snapshot
from app.services.signals.engine import evaluate_signals, persist_signals

settings = get_settings()


async def task_recompute_snapshot(ctx: dict, company_id: str) -> dict:
    """ARQ task: пересчитать снапшот для компании."""
    cid = uuid.UUID(company_id)
    async with AsyncSessionLocal() as db:
        # Устанавливаем RLS-контекст
        await db.execute(text("SELECT set_config('app.company_id', :cid, true)"), {"cid": company_id})
        snap = await recompute_snapshot(db, cid)

        # Оцениваем сигналы
        last_import = await db.execute(
            text(
                "SELECT MAX(updated_at) FROM import_batch "
                "WHERE company_id = :cid AND status IN ('done', 'partial')"
            ),
            {"cid": cid},
        )
        last_import_at = last_import.scalar()

        signals = await evaluate_signals(
            db, cid, snap.snapshot_date, snap.forecast_json, last_import_at
        )
        await persist_signals(db, cid, signals)
        await db.commit()

    return {"company_id": company_id, "snapshot_date": snap.snapshot_date.isoformat()}


async def task_send_telegram_digest(ctx: dict, company_id: str) -> dict:
    """ARQ task: отправить Telegram-дайджест собственнику."""
    from app.bot.digest import send_digest_for_company
    result = await send_digest_for_company(company_id)
    return result


async def startup(ctx: dict) -> None:
    pass


async def shutdown(ctx: dict) -> None:
    pass
