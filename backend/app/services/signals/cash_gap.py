"""
CashGapSignal — единый сигнал кассового разрыва.

Чистая функция без зависимостей от БД.
Используется в: dashboard.py, signals/engine.py, bot/digest.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class CashGapSignal:
    date: date
    is_stress: bool
    days_until: int
    severity: str  # critical | warning | info


def severity_for_days(days: int) -> str:
    if days <= 14:
        return "critical"
    if days <= 30:
        return "warning"
    return "info"


def compute_cash_gap_signal(
    forecast_json: dict,
    as_of: date,
) -> CashGapSignal | None:
    """
    B3: ранний кассовый разрыв из base или stress на горизонтах 14 → 30 → 91 дней.

    Severity:
      critical — ≤ 14 дней
      warning  — 15–30 дней
      info     — 31–90 дней

    Возвращает None, если разрыв не обнаружен.
    """
    horizon_pairs = [
        ("deficit_day_14", "deficit_day_14_stress"),
        ("deficit_day_30", "deficit_day_30_stress"),
        ("deficit_day_91", "deficit_day_91_stress"),
    ]

    for base_key, stress_key in horizon_pairs:
        base_val = forecast_json.get(base_key)
        stress_val = forecast_json.get(stress_key)

        if not base_val and not stress_val:
            continue

        # Выбираем ранний из двух
        if base_val and stress_val:
            if stress_val < base_val:
                chosen, is_stress = stress_val, True
            else:
                chosen, is_stress = base_val, False
        elif stress_val:
            chosen, is_stress = stress_val, True
        else:
            chosen, is_stress = base_val, False

        deficit_date = date.fromisoformat(chosen)
        days_until = (deficit_date - as_of).days

        if days_until < 0:
            continue

        return CashGapSignal(
            date=deficit_date,
            is_stress=is_stress,
            days_until=days_until,
            severity=severity_for_days(days_until),
        )

    return None
