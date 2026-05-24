"""
Unit-тесты: format_digest_message (Sprint A — c2+d2+c4+g2+e2).
"""
from datetime import date, timedelta

from app.services.signals.cash_gap import CashGapSignal
from bot.message_builder import format_digest_message, pick_top_reason

TODAY = date(2026, 5, 24)


def _msg(**kwargs) -> str:
    defaults = dict(
        snap_date=TODAY,
        balance=1_240_000.0,
        cash_gap=None,
        explain_headline="Остаток снизился на ₽80 000 за 7 дней",
        top_reason_label=None,
        top_reason_amount=None,
        top_reason_type=None,
        is_stale=False,
        stale_hours=None,
    )
    return format_digest_message(**{**defaults, **kwargs})


def test_date_in_header():
    msg = _msg()
    assert "24.05.2026" in msg


def test_balance_in_message():
    msg = _msg()
    assert "1" in msg and "240" in msg  # balance formatted


def test_no_cash_gap_no_gap_line():
    msg = _msg(cash_gap=None)
    assert "разрыв" not in msg.lower()


def test_critical_gap_line():
    gap = CashGapSignal(
        date=TODAY + timedelta(days=10),
        is_stress=False,
        days_until=10,
        severity="critical",
    )
    msg = _msg(cash_gap=gap)
    assert "Кассовый разрыв через 10 дн." in msg
    assert "⚠" in msg


def test_warning_gap_line():
    gap = CashGapSignal(
        date=TODAY + timedelta(days=25),
        is_stress=False,
        days_until=25,
        severity="warning",
    )
    msg = _msg(cash_gap=gap)
    assert "возможен" in msg


def test_info_gap_c4():
    """c4: info (31–90д) тоже показывается."""
    gap = CashGapSignal(
        date=TODAY + timedelta(days=60),
        is_stress=False,
        days_until=60,
        severity="info",
    )
    msg = _msg(cash_gap=gap)
    assert "ℹ" in msg
    assert "60 дн." in msg


def test_stress_note_in_gap():
    gap = CashGapSignal(
        date=TODAY + timedelta(days=12),
        is_stress=True,
        days_until=12,
        severity="critical",
    )
    msg = _msg(cash_gap=gap)
    assert "−15%" in msg


def test_stale_d2():
    msg = _msg(is_stale=True, stale_hours=30)
    assert "30 ч." in msg
    assert "Данные не обновлялись" in msg


def test_no_stale_no_stale_line():
    msg = _msg(is_stale=False)
    assert "не обновлялись" not in msg


def test_top_reason_shown():
    msg = _msg(
        top_reason_label="Списание: Аренда офиса",
        top_reason_amount=80_000.0,
        top_reason_type="debit",
    )
    assert "Аренда офиса" in msg
    assert "↓" in msg


# g2 — _pick_top_reason logic
def test_g2_declined_picks_debit():
    reasons = [
        {"type": "debit", "label": "Аренда", "amount": 80000},
        {"type": "credit", "label": "Клиент", "amount": 30000},
    ]
    label, amount, rtype = pick_top_reason(reasons, "Остаток снизился на ₽50 000")
    assert rtype == "debit"


def test_g2_grew_picks_credit():
    reasons = [
        {"type": "debit", "label": "Аренда", "amount": 30000},
        {"type": "credit", "label": "Клиент", "amount": 120000},
    ]
    label, amount, rtype = pick_top_reason(reasons, "Остаток вырос на ₽90 000")
    assert rtype == "credit"


def test_g2_fallback_obligations():
    reasons = [{"type": "obligations", "label": "Зарплата", "amount": 200000}]
    label, amount, rtype = pick_top_reason(reasons, "Нет транзакций за 7 дней")
    assert rtype == "obligations"


def test_g2_empty_reasons():
    label, amount, rtype = pick_top_reason([], "Остаток снизился")
    assert label is None
    assert amount is None
    assert rtype is None
