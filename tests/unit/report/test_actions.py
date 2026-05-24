"""Tests for rule-based recommended actions."""
from app.services.report.actions import build_recommended_actions


def test_stale_data_action():
    context = {
        "has_data": True,
        "stale": {"is_stale": True, "hours": 48},
    }
    actions = build_recommended_actions(context)
    assert any("48" in a for a in actions)


def test_cash_gap_critical_action():
    context = {
        "has_data": True,
        "stale": {"is_stale": False, "hours": None},
        "forecast": {
            "deficit_signal": {
                "date": "2026-06-15",
                "severity": "critical",
                "days_until": 10,
            }
        },
    }
    actions = build_recommended_actions(context)
    assert any("кассового разрыва" in a.lower() for a in actions)


def test_reconciliation_action():
    context = {
        "has_data": True,
        "stale": {"is_stale": False, "hours": None},
        "reconciliation": {
            "has_issues": True,
            "issues": [{"kind": "erp_only", "counterparty": "X", "detail": "test"}],
        },
    }
    actions = build_recommended_actions(context)
    assert any("1С" in a for a in actions)


def test_overdue_receivables_action():
    context = {
        "has_data": True,
        "stale": {"is_stale": False, "hours": None},
        "receivables": {
            "buckets": [{"bucket": "overdue", "amount": 50000, "count": 2}],
        },
    }
    actions = build_recommended_actions(context)
    assert any("просрочен" in a.lower() for a in actions)


def test_no_data_action():
    context = {"has_data": False, "stale": {"is_stale": False, "hours": None}}
    actions = build_recommended_actions(context)
    assert any("выписк" in a.lower() for a in actions)


def test_all_clear_fallback():
    context = {
        "has_data": True,
        "stale": {"is_stale": False, "hours": None},
        "forecast": {},
    }
    actions = build_recommended_actions(context)
    assert len(actions) >= 1
