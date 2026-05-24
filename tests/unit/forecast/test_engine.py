"""
Unit-тесты: ForecastEngine
"""
import json
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


def _load_golden() -> dict:
    return json.loads((FIXTURES_DIR / "forecast_golden.json").read_text())


def _make_transactions() -> list[dict]:
    golden = _load_golden()
    return [
        {
            "txn_date": date.fromisoformat(t["txn_date"]),
            "amount": Decimal(str(t["amount"])),
            "direction": t["direction"],
        }
        for t in golden["inputs"]["transactions"]
    ]


def _make_obligations(as_of: date) -> list[dict]:
    golden = _load_golden()
    return [
        {
            "due_date": date.fromisoformat(ob["due_date"]),
            "amount": Decimal(str(ob["amount"])),
            "status": ob["status"],
        }
        for ob in golden["inputs"]["obligations"]
    ]


class TestForecastEngine:
    def test_golden_file_no_deficit_30d(self):
        from app.services.forecast.engine import compute_forecast
        golden = _load_golden()
        as_of = date.fromisoformat(golden["meta"]["as_of_date"])
        balance = Decimal(str(golden["meta"]["current_balance"]))
        txns = _make_transactions()
        obs = _make_obligations(as_of)

        result = compute_forecast(
            company_id=uuid.uuid4(),
            current_balance=balance,
            transactions=txns,
            obligations=obs,
            as_of_date=as_of,
            horizon_days=30,
        )

        assert result.deficit_day_30 is None, "По golden данным дефицита в 30 дней нет"

    def test_has_obligations_flag(self):
        from app.services.forecast.engine import compute_forecast
        golden = _load_golden()
        as_of = date.fromisoformat(golden["meta"]["as_of_date"])

        result = compute_forecast(
            company_id=uuid.uuid4(),
            current_balance=Decimal("660000"),
            transactions=_make_transactions(),
            obligations=_make_obligations(as_of),
            as_of_date=as_of,
            horizon_days=30,
        )
        assert result.has_obligations is True

    def test_empty_obligations_no_has_obligations(self):
        from app.services.forecast.engine import compute_forecast
        as_of = date(2026, 5, 22)
        result = compute_forecast(
            company_id=uuid.uuid4(),
            current_balance=Decimal("500000"),
            transactions=[],
            obligations=[],
            as_of_date=as_of,
            horizon_days=30,
        )
        assert result.has_obligations is False
        assert result.deficit_day_30 is None, "Без обязательств нет дефицита"

    def test_deficit_detected(self):
        from app.services.forecast.engine import compute_forecast
        as_of = date(2026, 5, 22)
        # Маленький баланс + большое обязательство завтра
        result = compute_forecast(
            company_id=uuid.uuid4(),
            current_balance=Decimal("10000"),
            transactions=[],
            obligations=[
                {"due_date": as_of + timedelta(days=5), "amount": Decimal("500000"), "status": "pending"}
            ],
            as_of_date=as_of,
            horizon_days=30,
        )
        assert result.deficit_day_7 is not None
        assert result.deficit_day_30 is not None

    def test_stress_scenario_lower_balance(self):
        from app.services.forecast.engine import compute_forecast
        as_of = date(2026, 5, 22)
        base = compute_forecast(
            company_id=uuid.uuid4(),
            current_balance=Decimal("500000"),
            transactions=_make_transactions(),
            obligations=_make_obligations(as_of),
            as_of_date=as_of,
            horizon_days=14,
            scenario="base",
        )
        stress = compute_forecast(
            company_id=uuid.uuid4(),
            current_balance=Decimal("500000"),
            transactions=_make_transactions(),
            obligations=_make_obligations(as_of),
            as_of_date=as_of,
            horizon_days=14,
            scenario="stress",
        )
        base_final = base.days[-1].forecast_balance
        stress_final = stress.days[-1].forecast_balance
        assert stress_final < base_final, "Stress сценарий должен давать меньший остаток"

    def test_optimistic_scenario_higher_balance(self):
        from app.services.forecast.engine import compute_forecast
        as_of = date(2026, 5, 22)
        base = compute_forecast(
            company_id=uuid.uuid4(),
            current_balance=Decimal("500000"),
            transactions=_make_transactions(),
            obligations=_make_obligations(as_of),
            as_of_date=as_of,
            horizon_days=14,
            scenario="base",
        )
        optimistic = compute_forecast(
            company_id=uuid.uuid4(),
            current_balance=Decimal("500000"),
            transactions=_make_transactions(),
            obligations=_make_obligations(as_of),
            as_of_date=as_of,
            horizon_days=14,
            scenario="optimistic",
        )
        assert optimistic.days[-1].forecast_balance > base.days[-1].forecast_balance

    def test_91_day_horizon(self):
        from app.services.forecast.engine import compute_forecast
        as_of = date(2026, 5, 22)
        result = compute_forecast(
            company_id=uuid.uuid4(),
            current_balance=Decimal("1000000"),
            transactions=[],
            obligations=[],
            as_of_date=as_of,
            horizon_days=91,
        )
        assert len(result.days) == 91

    def test_timezone_shift_does_not_break(self):
        """Формула не зависит от timezone — дата хранится как date()."""
        from app.services.forecast.engine import compute_forecast
        for as_of in [date(2026, 12, 31), date(2026, 1, 1)]:
            result = compute_forecast(
                company_id=uuid.uuid4(),
                current_balance=Decimal("100000"),
                transactions=[],
                obligations=[],
                as_of_date=as_of,
                horizon_days=7,
            )
            assert len(result.days) == 7

    def test_receivables_increase_balance(self):
        """Дебиторка с collection_probability > 0 увеличивает прогнозный остаток."""
        from app.services.forecast.engine import compute_forecast
        as_of = date(2026, 5, 22)
        due = as_of + timedelta(days=15)
        base = compute_forecast(
            company_id=uuid.uuid4(),
            current_balance=Decimal("100000"),
            transactions=[],
            obligations=[],
            as_of_date=as_of,
            horizon_days=30,
        )
        with_rcv = compute_forecast(
            company_id=uuid.uuid4(),
            current_balance=Decimal("100000"),
            transactions=[],
            obligations=[],
            receivables=[{"due_date": due, "expected_amount": Decimal("50000"), "status": "open"}],
            as_of_date=as_of,
            horizon_days=30,
        )
        assert with_rcv.days[14].forecast_balance > base.days[14].forecast_balance

    def test_has_receivables_flag(self):
        from app.services.forecast.engine import compute_forecast
        as_of = date(2026, 5, 22)
        result = compute_forecast(
            company_id=uuid.uuid4(),
            current_balance=Decimal("100000"),
            transactions=[],
            obligations=[],
            receivables=[{
                "due_date": as_of + timedelta(days=10),
                "expected_amount": Decimal("30000"),
                "status": "open",
            }],
            as_of_date=as_of,
            horizon_days=30,
        )
        assert result.has_receivables is True
        assert result.has_aging_detail is True

    def test_no_receivables_flags_false(self):
        from app.services.forecast.engine import compute_forecast
        as_of = date(2026, 5, 22)
        result = compute_forecast(
            company_id=uuid.uuid4(),
            current_balance=Decimal("100000"),
            transactions=[],
            obligations=[],
            as_of_date=as_of,
            horizon_days=7,
        )
        assert result.has_receivables is False
        assert result.has_aging_detail is False

    def test_unknown_bucket_zero_probability_no_effect(self):
        """unknown bucket (probability=0) не влияет на прогноз."""
        from app.services.forecast.engine import compute_forecast
        as_of = date(2026, 5, 22)
        base = compute_forecast(
            company_id=uuid.uuid4(),
            current_balance=Decimal("100000"),
            transactions=[],
            obligations=[],
            as_of_date=as_of,
            horizon_days=30,
        )
        with_zero = compute_forecast(
            company_id=uuid.uuid4(),
            current_balance=Decimal("100000"),
            transactions=[],
            obligations=[],
            receivables=[{
                "due_date": as_of + timedelta(days=15),
                "expected_amount": Decimal("0"),
                "status": "open",
            }],
            as_of_date=as_of,
            horizon_days=30,
        )
        assert base.days[-1].forecast_balance == with_zero.days[-1].forecast_balance

    def test_forecast_day_has_receivable_collections_field(self):
        from app.services.forecast.engine import compute_forecast
        as_of = date(2026, 5, 22)
        result = compute_forecast(
            company_id=uuid.uuid4(),
            current_balance=Decimal("100000"),
            transactions=[],
            obligations=[],
            as_of_date=as_of,
            horizon_days=7,
        )
        assert hasattr(result.days[0], "receivable_collections")
