"""
Telegram Bot — aiogram 3.x

Sprint 1b: ежедневный дайджест в 08:00 MSK.
Sprint A: format_digest_message вынесен в bot/message_builder.py.
"""
from __future__ import annotations

import logging
from datetime import date

import httpx
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode

from app.core.config import get_settings
from bot.message_builder import format_digest_message, pick_top_reason

settings = get_settings()
logger = logging.getLogger(__name__)

bot = Bot(token=settings.telegram_bot_token, parse_mode=ParseMode.HTML) if settings.telegram_bot_token else None
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    await message.answer(
        "👋 Добро пожаловать в <b>Финансовый автопилот</b>!\n\n"
        "Я буду присылать ежедневную сводку о финансах вашей компании в 08:00 МСК.\n\n"
        "Для подключения: откройте личный кабинет → Telegram → нажмите «Получить код» "
        "и отправьте мне команду <code>/connect 123456</code>."
    )


@dp.message(Command("status"))
async def cmd_status(message: types.Message) -> None:
    await message.answer("Используйте /start для начала работы или откройте веб-приложение.")


@dp.message(Command("connect"))
async def cmd_connect(message: types.Message) -> None:
    """
    /connect 123456 — привязать аккаунт по одноразовому коду.
    Бот смотрит код в Redis (ключ connect:{code}), получает user_id,
    затем вызывает внутренний endpoint для обновления telegram_chat_id.
    """
    import redis.asyncio as aioredis

    text_parts = (message.text or "").strip().split()
    if len(text_parts) < 2 or not text_parts[1].isdigit() or len(text_parts[1]) != 6:
        await message.answer(
            "⚠️ Укажите 6-значный код: <code>/connect 123456</code>\n\n"
            "Код можно получить в личном кабинете → Telegram → «Получить код»."
        )
        return

    code = text_parts[1]
    chat_id = str(message.chat.id)

    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        user_id = await redis_client.get(f"connect:{code}")
        if not user_id:
            await message.answer(
                "❌ Код не найден или истёк. Запросите новый код в личном кабинете."
            )
            return
        await redis_client.delete(f"connect:{code}")
    finally:
        await redis_client.aclose()

    try:
        headers = {}
        if settings.telegram_webhook_secret:
            headers["X-Internal-Secret"] = settings.telegram_webhook_secret
        async with httpx.AsyncClient(base_url=settings.backend_url, timeout=10) as client:
            resp = await client.patch(
                "/auth/internal/set-telegram",
                json={"user_id": user_id, "telegram_chat_id": chat_id},
                headers=headers,
            )
            resp.raise_for_status()
    except Exception as exc:
        logger.error("Failed to link telegram for user %s: %s", user_id, exc)
        await message.answer("⚠️ Не удалось привязать аккаунт. Попробуйте позже.")
        return

    await message.answer(
        "✅ <b>Аккаунт привязан!</b>\n\n"
        "Теперь вы будете получать ежедневный финансовый дайджест в 08:00 МСК."
    )


async def send_digest_for_company(company_id: str) -> dict:
    """
    Отправляет дайджест всем подписанным пользователям компании.
    Вызывается из ARQ worker.
    """
    from sqlalchemy import text
    from app.core.database import AsyncSessionLocal
    from app.services.explain.engine import explain_balance_change
    from app.services.signals.cash_gap import compute_cash_gap_signal
    import uuid
    from datetime import datetime, timezone

    cid = uuid.UUID(company_id)
    today = date.today()
    sent_count = 0

    async with AsyncSessionLocal() as db:
        await db.execute(
            text("SELECT set_config('app.company_id', :cid, true)"), {"cid": company_id}
        )

        users_result = await db.execute(
            text(
                'SELECT telegram_chat_id FROM "user" '
                "WHERE company_id = :cid AND telegram_chat_id IS NOT NULL AND is_active = true"
            ),
            {"cid": cid},
        )
        chat_ids = [r[0] for r in users_result.fetchall()]

        if not chat_ids:
            return {"sent": 0, "company_id": company_id}

        snap_result = await db.execute(
            text(
                "SELECT balance, forecast_json FROM daily_cash_snapshot "
                "WHERE company_id = :cid AND snapshot_date = :today"
            ),
            {"cid": cid, "today": today},
        )
        snap = snap_result.fetchone()

        if snap is None:
            text_msg = (
                "📊 <b>Финансовый автопилот</b>\n\n"
                "⚠️ Данные пока не загружены. Загрузите банковскую выписку в личном кабинете."
            )
        else:
            balance = float(snap[0])
            forecast_json = snap[1]

            last_import_row = await db.execute(
                text(
                    "SELECT MAX(updated_at) FROM import_batch "
                    "WHERE company_id = :cid AND status IN ('done', 'partial')"
                ),
                {"cid": cid},
            )
            last_import_at = last_import_row.scalar()
            is_stale = False
            stale_hours = None
            if last_import_at:
                now_utc = datetime.now(timezone.utc)
                last_aware = (
                    last_import_at if last_import_at.tzinfo
                    else last_import_at.replace(tzinfo=timezone.utc)
                )
                hours = (now_utc - last_aware).total_seconds() / 3600
                is_stale = hours > 24
                stale_hours = int(hours) if is_stale else None

            explain = await explain_balance_change(db, cid, today)
            cash_gap = compute_cash_gap_signal(forecast_json, today)

            reason_label, reason_amount, reason_type = pick_top_reason(
                [{"type": r.type, "label": r.label, "amount": r.amount} for r in explain.reasons],
                explain.headline,
            )

            text_msg = format_digest_message(
                snap_date=today,
                balance=balance,
                cash_gap=cash_gap,
                explain_headline=explain.headline,
                top_reason_label=reason_label,
                top_reason_amount=reason_amount,
                top_reason_type=reason_type,
                is_stale=is_stale,
                stale_hours=stale_hours,
            )

        for chat_id in chat_ids:
            if not bot:
                logger.warning("TELEGRAM_BOT_TOKEN не настроен — дайджест не отправляется")
                break
            try:
                await bot.send_message(chat_id=chat_id, text=text_msg)
                sent_count += 1
            except Exception as exc:
                logger.warning("Failed to send digest to %s: %s", chat_id, exc)

    return {"sent": sent_count, "company_id": company_id}
