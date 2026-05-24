"""
Telegram Bot — aiogram 3.x

Sprint 1b: ежедневный дайджест в 08:00 MSK.
Sprint 2+: алерты дефицита, ответы на вопросы.
"""
from __future__ import annotations

import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

bot = Bot(token=settings.telegram_bot_token, parse_mode=ParseMode.HTML) if settings.telegram_bot_token else None
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    await message.answer(
        "👋 Добро пожаловать в <b>Финансовый автопилот</b>!\n\n"
        "Я буду присылать ежедневную сводку о финансах вашей компании в 08:00 МСК.\n\n"
        "Для подключения: войдите в личный кабинет и привяжите Telegram-аккаунт."
    )


@dp.message(Command("status"))
async def cmd_status(message: types.Message) -> None:
    await message.answer("Используйте /start для начала работы или откройте веб-приложение.")


async def send_digest_for_company(company_id: str) -> dict:
    """
    Отправляет дайджест всем подписанным пользователям компании.
    Вызывается из ARQ worker.
    """
    from sqlalchemy import text
    from app.core.database import AsyncSessionLocal
    import uuid

    cid = uuid.UUID(company_id)
    sent_count = 0

    async with AsyncSessionLocal() as db:
        await db.execute(
            text("SELECT set_config('app.company_id', :cid, true)"), {"cid": company_id}
        )

        # Получаем пользователей с telegram_chat_id
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

        # Получаем снапшот
        from datetime import date
        snap_result = await db.execute(
            text(
                "SELECT balance, forecast_json FROM daily_cash_snapshot "
                "WHERE company_id = :cid AND snapshot_date = :today"
            ),
            {"cid": cid, "today": date.today()},
        )
        snap = snap_result.fetchone()

        if snap is None:
            text_msg = (
                "📊 <b>Финансовый автопилот</b>\n\n"
                "⚠️ Данные пока не загружены. Загрузите банковскую выписку в личном кабинете."
            )
        else:
            balance = float(snap[0])
            forecast = snap[1]
            deficit_14 = forecast.get("deficit_day_14")

            deficit_line = ""
            if deficit_14:
                from datetime import datetime
                d = date.fromisoformat(deficit_14)
                days_left = (d - date.today()).days
                deficit_line = f"\n⚠️ <b>Кассовый разрыв</b> через {days_left} дней ({d.strftime('%d.%m')})"

            text_msg = (
                f"📊 <b>Финансовый автопилот</b> — {date.today().strftime('%d.%m.%Y')}\n\n"
                f"💰 Остаток: <b>₽{balance:,.0f}</b>".replace(",", " ")
                + deficit_line
                + "\n\n<i>Открыть подробности →</i> личный кабинет"
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
