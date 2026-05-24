"""
ForecastEngine — детерминированный прогноз кеша.

Sprint 1 (bank-only):
  forecast_balance[d] = balance[d-1]
                      + median_daily_inflow_7d   # fallback: нет истории → 0
                      - planned_obligations[d]   # ручной ввод

Sprint 2+ (полная формула):
  + planned_inflows[d]
  + expected_receivable_collections[d]
  - recurring_pattern[d]

Сценарии: base=1.0, stress(inflow×0.85/outflow×1.1), optimistic(inflow×1.1/outflow×0.9)
"""
from __future__ import annotations

import statistics
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

ScenarioType = Literal["base", "stress", "optimistic"]

SCENARIO_MULTIPLIERS: dict[ScenarioType, tuple[float, float]] = {
    "base": (1.0, 1.0),
    "stress": (0.85, 1.1),
    "optimistic": (1.1, 0.9),
}


@dataclass
class ForecastDay:
    day: date
    forecast_balance: Decimal
    inflow_estimate: Decimal
    outflow_obligations: Decimal
    receivable_collections: Decimal
    scenario: ScenarioType


@dataclass
class ForecastResult:
    company_id: uuid.UUID
    as_of_date: date
    current_balance: Decimal
    horizon_days: int
    days: list[ForecastDay]
    has_obligations: bool
    has_receivables: bool
    has_aging_detail: bool
    # Первый день дефицита по горизонтам
    deficit_day_7: date | None = None
    deficit_day_14: date | None = None
    deficit_day_30: date | None = None
    deficit_day_91: date | None = None


def _median_daily_inflow(
    transactions: list[dict],  # [{txn_date, amount, direction}]
    as_of: date,
    lookback_days: int = 7,
) -> Decimal:
    """Медиана ежедневных поступлений за последние N дней."""
    since = as_of - timedelta(days=lookback_days)
    credits_by_day: dict[date, Decimal] = {}
    for t in transactions:
        if t["direction"] == "credit" and since <= t["txn_date"] <= as_of:
            d = t["txn_date"]
            credits_by_day[d] = credits_by_day.get(d, Decimal(0)) + t["amount"]

    if not credits_by_day:
        return Decimal(0)

    daily_values = list(credits_by_day.values())
    return Decimal(str(statistics.median(float(v) for v in daily_values)))


def compute_forecast(
    company_id: uuid.UUID,
    current_balance: Decimal,
    transactions: list[dict],
    obligations: list[dict],  # [{due_date, amount, status}]
    as_of_date: date,
    horizon_days: int = 91,
    scenario: ScenarioType = "base",
    receivables: list[dict] | None = None,  # [{due_date, expected_amount, status}]
) -> ForecastResult:
    """
    Вычисляет детерминированный прогноз остатка.

    transactions: список dict {txn_date: date, amount: Decimal, direction: str}
    obligations:  список dict {due_date: date, amount: Decimal, status: str}
    receivables:  список dict {due_date: date, expected_amount: Decimal, status: str}
                  (expected_amount = amount * collection_probability)
    """
    inflow_multiplier, outflow_multiplier = SCENARIO_MULTIPLIERS[scenario]

    median_inflow = _median_daily_inflow(transactions, as_of_date)
    median_inflow_adjusted = Decimal(str(float(median_inflow) * inflow_multiplier))

    pending_obligations: dict[date, Decimal] = {}
    for ob in obligations:
        if ob["status"] == "pending" and ob["due_date"] >= as_of_date:
            d = ob["due_date"]
            pending_obligations[d] = pending_obligations.get(d, Decimal(0)) + ob["amount"]

    has_obligations = bool(pending_obligations)

    # Группируем дебиторку по due_date; только open/overdue
    receivable_by_day: dict[date, Decimal] = {}
    _receivables = receivables or []
    for rcv in _receivables:
        if rcv["status"] in ("open", "overdue") and rcv["due_date"] >= as_of_date:
            d = rcv["due_date"]
            receivable_by_day[d] = receivable_by_day.get(d, Decimal(0)) + rcv["expected_amount"]

    has_receivables = bool(receivable_by_day)
    has_aging_detail = bool(_receivables)

    days: list[ForecastDay] = []
    balance = current_balance
    deficit_days: dict[int, date | None] = {7: None, 14: None, 30: None, 91: None}

    for offset in range(1, horizon_days + 1):
        day = as_of_date + timedelta(days=offset)
        obligations_today = pending_obligations.get(day, Decimal(0))
        obligations_adjusted = Decimal(str(float(obligations_today) * outflow_multiplier))

        receivables_today = receivable_by_day.get(day, Decimal(0))
        receivables_adjusted = Decimal(str(float(receivables_today) * inflow_multiplier))

        balance = balance + median_inflow_adjusted + receivables_adjusted - obligations_adjusted

        days.append(
            ForecastDay(
                day=day,
                forecast_balance=balance,
                inflow_estimate=median_inflow_adjusted,
                outflow_obligations=obligations_adjusted,
                receivable_collections=receivables_adjusted,
                scenario=scenario,
            )
        )

        if balance < 0:
            for horizon in [7, 14, 30, 91]:
                if offset <= horizon and deficit_days[horizon] is None:
                    deficit_days[horizon] = day

    return ForecastResult(
        company_id=company_id,
        as_of_date=as_of_date,
        current_balance=current_balance,
        horizon_days=horizon_days,
        days=days,
        has_obligations=has_obligations,
        has_receivables=has_receivables,
        has_aging_detail=has_aging_detail,
        deficit_day_7=deficit_days[7],
        deficit_day_14=deficit_days[14],
        deficit_day_30=deficit_days[30],
        deficit_day_91=deficit_days[91],
    )
