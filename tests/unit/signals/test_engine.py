"""
Unit-тесты: SignalEngine
"""
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest


class TestSignalEngine:
    @pytest.mark.asyncio
    async def test_deficit_7d_signal(self):
        from app.services.signals.engine import evaluate_signals
        company_id = uuid.uuid4()
        as_of = date(2026, 5, 22)
        deficit_date = (as_of + timedelta(days=5)).isoformat()

        forecast_json = {
            "deficit_day_7": deficit_date,
            "deficit_day_14": None,
            "deficit_day_30": None,
            "deficit_day_91": None,
            "has_obligations": True,
        }
        signals = await evaluate_signals(
            db=None,  # evaluate_signals не обращается к БД напрямую
            company_id=company_id,
            as_of=as_of,
            forecast_json=forecast_json,
            last_import_at=datetime.utcnow(),
        )
        types = [s.alert_type for s in signals]
        assert "deficit_7d" in types

    @pytest.mark.asyncio
    async def test_stale_data_signal(self):
        from app.services.signals.engine import evaluate_signals
        company_id = uuid.uuid4()
        as_of = date(2026, 5, 22)

        forecast_json = {"has_obligations": True}
        old_import = datetime.utcnow() - timedelta(hours=25)

        signals = await evaluate_signals(
            db=None,
            company_id=company_id,
            as_of=as_of,
            forecast_json=forecast_json,
            last_import_at=old_import,
        )
        types = [s.alert_type for s in signals]
        assert "stale_data" in types

    @pytest.mark.asyncio
    async def test_no_stale_signal_if_fresh(self):
        from app.services.signals.engine import evaluate_signals
        company_id = uuid.uuid4()
        as_of = date(2026, 5, 22)

        forecast_json = {"has_obligations": True}
        fresh_import = datetime.utcnow() - timedelta(hours=1)

        signals = await evaluate_signals(
            db=None,
            company_id=company_id,
            as_of=as_of,
            forecast_json=forecast_json,
            last_import_at=fresh_import,
        )
        types = [s.alert_type for s in signals]
        assert "stale_data" not in types

    @pytest.mark.asyncio
    async def test_no_obligations_signal(self):
        from app.services.signals.engine import evaluate_signals
        company_id = uuid.uuid4()
        as_of = date(2026, 5, 22)

        forecast_json = {"has_obligations": False}

        signals = await evaluate_signals(
            db=None,
            company_id=company_id,
            as_of=as_of,
            forecast_json=forecast_json,
            last_import_at=datetime.utcnow(),
        )
        types = [s.alert_type for s in signals]
        assert "no_obligations" in types

    @pytest.mark.asyncio
    async def test_multiple_accounts_no_deficit(self):
        from app.services.signals.engine import evaluate_signals
        company_id = uuid.uuid4()
        as_of = date(2026, 5, 22)

        forecast_json = {
            "deficit_day_7": None,
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
            last_import_at=datetime.utcnow(),
        )
        deficit_signals = [s for s in signals if "deficit" in s.alert_type]
        assert len(deficit_signals) == 0
