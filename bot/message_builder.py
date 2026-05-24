"""
Форматирование текстовых сообщений для Telegram-дайджеста.

Чистые функции без зависимостей от aiogram — можно тестировать изолированно.
"""
from __future__ import annotations

from datetime import date

from app.services.signals.cash_gap import CashGapSignal


def format_digest_message(
    snap_date: date,
    balance: float,
    cash_gap: CashGapSignal | None,
    explain_headline: str,
    top_reason_label: str | None,
    top_reason_amount: float | None,
    top_reason_type: str | None,
    is_stale: bool,
    stale_hours: int | None,
) -> str:
    """
    Форматирует текст ежедневного дайджеста.

    c2: остаток + headline + top_reason (g2)
    c4: сигнал разрыва до 90 дней (если есть)
    d2: строка stale, если данные > 24 ч
    e2: emoji и формулировка по severity
    """
    balance_str = f"₽\u00a0{balance:,.0f}".replace(",", "\u00a0")
    lines: list[str] = [
        f"📊 <b>Финансовый автопилот</b> — {snap_date.strftime('%d.%m.%Y')}",
        "",
        f"💰 Остаток: <b>{balance_str}</b>",
        explain_headline,
    ]

    # top_reason — g2: по направлению изменения
    if top_reason_label and top_reason_amount is not None:
        icon = {"debit": "↓", "credit": "↑", "obligations": "📅"}.get(
            top_reason_type or "", "•"
        )
        amount_str = f"₽\u00a0{top_reason_amount:,.0f}".replace(",", "\u00a0")
        lines.append(f"{icon} {top_reason_label} — {amount_str}")

    # c4 + e2: разрыв до 90 дней
    if cash_gap is not None:
        stress_note = " · если поступления −15%" if cash_gap.is_stress else ""
        if cash_gap.severity == "critical":
            gap_icon = "⚠"
            verb = f"Кассовый разрыв через {cash_gap.days_until} дн."
        elif cash_gap.severity == "warning":
            gap_icon = "⚠"
            verb = f"Кассовый разрыв возможен через {cash_gap.days_until} дн."
        else:
            gap_icon = "ℹ"
            verb = f"Риск кассового разрыва через {cash_gap.days_until} дн."

        lines.append("")
        lines.append(
            f"{gap_icon} <b>{verb}</b> ({cash_gap.date.strftime('%d.%m')}){stress_note}"
        )

    # d2: stale
    if is_stale and stale_hours:
        lines.append(f"⚠ Данные не обновлялись {stale_hours} ч. — загрузите выписку")

    lines.append("")
    lines.append("<i>Открыть подробности →</i> личный кабинет")

    return "\n".join(lines)


def pick_top_reason(
    reasons: list[dict],
    headline: str,
) -> tuple[str | None, float | None, str | None]:
    """
    g2: выбирает одну причину по направлению изменения остатка.
    headline «снизился» → debit, «вырос» → credit, иначе → obligations.
    """
    if not reasons:
        return None, None, None

    if "снизился" in headline:
        target_type = "debit"
    elif "вырос" in headline:
        target_type = "credit"
    else:
        target_type = "obligations"

    for r in reasons:
        if r["type"] == target_type:
            return r["label"], r["amount"], r["type"]

    first = reasons[0]
    return first["label"], first["amount"], first["type"]
