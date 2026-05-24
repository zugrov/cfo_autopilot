"""
Reconciler — сверка дебиторки 1С с банковскими поступлениями (ADR-0002).

Типы расхождений:
  erp_only        — есть в 1С, нет отражения в банке
  bank_only       — есть в банке, нет в 1С
  amount_mismatch — контрагент совпал, суммы расходятся
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

IssueKind = Literal["erp_only", "bank_only", "amount_mismatch"]

_PREFIXES = ("ооо", "ooo", "ип", "зао", "zao", "пао", "pao", "ао", "ao")
_MAX_ISSUES = 10


@dataclass
class ReconciliationIssue:
    kind: IssueKind
    counterparty: str
    amount: float
    detail: str


def normalize_name(name: str) -> str:
    """Нормализация названия контрагента для сопоставления."""
    n = name.strip().lower()
    n = n.replace("«", "").replace("»", "").replace('"', "").replace("'", "")
    n = re.sub(r"\s+", " ", n)
    for prefix in _PREFIXES:
        if n.startswith(prefix + " "):
            n = n[len(prefix) + 1 :].strip()
            break
    return n


def _aggregate_credits(
    bank_credits: list[dict],
    since: date,
) -> tuple[dict[str, float], dict[str, str]]:
    """Сумма поступлений и display-name по normalized key."""
    totals: dict[str, float] = {}
    display: dict[str, str] = {}
    for item in bank_credits:
        txn_date = item["txn_date"]
        if txn_date < since:
            continue
        key = normalize_name(item["counterparty"] or "")
        if not key:
            continue
        amt = float(item["amount"])
        totals[key] = totals.get(key, 0.0) + amt
        display.setdefault(key, item["counterparty"] or key)
    return totals, display


def _aggregate_receivables(
    receivables: list[dict],
    as_of: date,
) -> tuple[dict[str, float], dict[str, float], dict[str, str]]:
    """
    open totals, due totals (due_date <= as_of), display names.
    """
    open_totals: dict[str, float] = {}
    due_totals: dict[str, float] = {}
    display: dict[str, str] = {}
    for item in receivables:
        key = normalize_name(item["counterparty"] or "")
        if not key:
            continue
        amt = float(item["amount"])
        open_totals[key] = open_totals.get(key, 0.0) + amt
        display.setdefault(key, item["counterparty"] or key)
        due_date = item["due_date"]
        if due_date <= as_of:
            due_totals[key] = due_totals.get(key, 0.0) + amt
    return open_totals, due_totals, display


def _relative_diff(a: float, b: float) -> float:
    denom = max(a, b, 1.0)
    return abs(a - b) / denom


def compute_reconciliation(
    receivables: list[dict],
    bank_credits: list[dict],
    as_of: date,
    lookback_days: int = 90,
    mismatch_threshold_pct: float = 0.10,
) -> list[ReconciliationIssue]:
    """
    receivables: {counterparty, amount, due_date, status}
    bank_credits: {counterparty, amount, txn_date}
    """
    if not receivables or not bank_credits:
        return []

    since = as_of - timedelta(days=lookback_days)
    bank_totals, bank_display = _aggregate_credits(bank_credits, since)
    open_totals, due_totals, rcv_display = _aggregate_receivables(receivables, as_of)

    if not bank_totals or not open_totals:
        return []

    all_keys = set(bank_totals.keys()) | set(open_totals.keys())
    issues: list[ReconciliationIssue] = []

    for key in all_keys:
        bank_amt = bank_totals.get(key, 0.0)
        open_amt = open_totals.get(key, 0.0)
        due_amt = due_totals.get(key, 0.0)
        label = rcv_display.get(key) or bank_display.get(key) or key

        if due_amt > 0 and bank_amt == 0:
            issues.append(
                ReconciliationIssue(
                    kind="erp_only",
                    counterparty=label,
                    amount=due_amt,
                    detail=f"Дебиторка {due_amt:,.0f} ₽ просрочена или к оплате, поступлений в банке нет",
                )
            )
        elif bank_amt > 0 and open_amt == 0:
            issues.append(
                ReconciliationIssue(
                    kind="bank_only",
                    counterparty=label,
                    amount=bank_amt,
                    detail=f"Поступление {bank_amt:,.0f} ₽ в банке, нет открытой дебиторки в 1С",
                )
            )
        elif bank_amt > 0 and open_amt > 0:
            if _relative_diff(bank_amt, open_amt) > mismatch_threshold_pct:
                issues.append(
                    ReconciliationIssue(
                        kind="amount_mismatch",
                        counterparty=label,
                        amount=max(bank_amt, open_amt),
                        detail=(
                            f"Банк {bank_amt:,.0f} ₽ vs 1С {open_amt:,.0f} ₽ "
                            f"(расхождение > {int(mismatch_threshold_pct * 100)}%)"
                        ),
                    )
                )

    issues.sort(key=lambda x: x.amount, reverse=True)
    return issues[:_MAX_ISSUES]
