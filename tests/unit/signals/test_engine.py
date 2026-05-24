"""
Unit-тесты: SignalEngine (Sprint A — только cash_gap).
"""
import uuid
from datetime import date, timedelta

import pytest


class TestSignalEngine:
    @pytest.mark.asyncio
    async def test_cash_gap_signal_created(self):
        from app.services.signals.engine import evaluate_signals
        company_id = uuid.uuid4()
        as_of = date(2026, 5, 22)
        deficit_date = (as_of + timedelta(days=10)).isoformat()

        forecast_json = {
            "deficit_day_14": deficit_date,
            "has_obligations": True,
        }
        signals = await evaluate_signals(
            db=None,
            company_id=company_id,
            as_of=as_of,
            forecast_json=forecast_json,
        )
        types = [s.alert_type for s in signals]
        assert "cash_gap" in types
        gap = signals[0]
        assert gap.severity == "critical"

    @pytest.mark.asyncio
    async def test_no_signal_if_no_deficit(self):
        from app.services.signals.engine import evaluate_signals
        company_id = uuid.uuid4()
        as_of = date(2026, 5, 22)

        forecast_json = {
            "deficit_day_14": None,
            "deficit_day_30": None,
            "deficit_day_91": None,
            "has_obligations": True,
        }
        signals = await evaluate_signals(
            db=None,
            company_id=company_id,
            as_of=as_of,
            forecast_json=forecast_json,
        )
        assert signals == []
