"""
ARQ Workers — фоновые задачи.

Задачи:
- recompute_snapshot: пересчёт daily_cash_snapshot после импорта
- send_telegram_digest: отправка ежедневного дайджеста в 08:00 MSK
- send_weekly_report: еженедельный PDF/email в понедельник 08:00 MSK

Запуск: arq app.workers.settings.WorkerSettings
"""
from __future__ import annotations

import logging
import uuid
from datetime import date

from arq import ArqRedis
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.services.forecast.snapshot import recompute_snapshot
from app.services.report.service import send_weekly_report_for_company
from app.services.signals.engine import evaluate_signals, persist_signals

settings = get_settings()
logger = logging.getLogger(__name__)


async def task_recompute_snapshot(ctx: dict, company_id: str) -> dict:
    """ARQ task: пересчитать снапшот для компании."""
    cid = uuid.UUID(company_id)
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.company_id', :cid, true)"), {"cid": company_id})
        snap = await recompute_snapshot(db, cid)

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


async def task_dispatch_daily_digests(ctx: dict) -> dict:
    """Fan-out: ежедневный Telegram-дайджест для всех компаний."""
    redis: ArqRedis = ctx["redis"]
    async with AsyncSessionLocal() as db:
        rows = await db.execute(text("SELECT id FROM company"))
        company_ids = [str(r[0]) for r in rows.fetchall()]

    enqueued = 0
    for cid in company_ids:
        await redis.enqueue_job("task_send_telegram_digest", cid)
        enqueued += 1

    return {"enqueued": enqueued}


async def task_send_weekly_report(ctx: dict, company_id: str) -> dict:
    """ARQ task: отправить еженедельный PDF/email owner."""
    cid = uuid.UUID(company_id)
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("SELECT set_config('app.company_id', :cid, true)"),
            {"cid": company_id},
        )
        result = await send_weekly_report_for_company(db, cid, date.today())
        await db.commit()
    return result


async def task_dispatch_weekly_reports(ctx: dict) -> dict:
    """Fan-out: еженедельный PDF/email для всех компаний."""
    redis: ArqRedis = ctx["redis"]
    async with AsyncSessionLocal() as db:
        rows = await db.execute(text("SELECT id FROM company"))
        company_ids = [str(r[0]) for r in rows.fetchall()]

    enqueued = 0
    for cid in company_ids:
        await redis.enqueue_job("task_send_weekly_report", cid)
        enqueued += 1

    return {"enqueued": enqueued}


async def startup(ctx: dict) -> None:
    pass


async def shutdown(ctx: dict) -> None:
    pass
