"""
Unit-тесты: compute_cash_gap_signal (Sprint A).
"""
from datetime import date, timedelta

from app.services.signals.cash_gap import compute_cash_gap_signal, CashGapSignal


def _fj(**kwargs) -> dict:
    """Создаёт минимальный forecast_json с переданными полями."""
    return {
        "deficit_day_14": None,
        "deficit_day_14_stress": None,
        "deficit_day_30": None,
        "deficit_day_30_stress": None,
        "deficit_day_91": None,
        "deficit_day_91_stress": None,
        **kwargs,
    }


AS_OF = date(2026, 5, 24)


def test_no_deficit_returns_none():
    result = compute_cash_gap_signal(_fj(), AS_OF)
    assert result is None


def test_critical_base():
    gap_date = (AS_OF + timedelta(days=10)).isoformat()
    result = compute_cash_gap_signal(_fj(deficit_day_14=gap_date), AS_OF)
    assert result is not None
    assert result.severity == "critical"
    assert result.days_until == 10
    assert result.is_stress is False


def test_warning_30d():
    gap_date = (AS_OF + timedelta(days=20)).isoformat()
    result = compute_cash_gap_signal(_fj(deficit_day_30=gap_date), AS_OF)
    assert result is not None
    assert result.severity == "warning"
    assert result.days_until == 20
    assert result.is_stress is False


def test_info_91d():
    gap_date = (AS_OF + timedelta(days=45)).isoformat()
    result = compute_cash_gap_signal(_fj(deficit_day_91=gap_date), AS_OF)
    assert result is not None
    assert result.severity == "info"
    assert result.days_until == 45


def test_stress_earlier_than_base():
    base_date = (AS_OF + timedelta(days=20)).isoformat()
    stress_date = (AS_OF + timedelta(days=10)).isoformat()
    result = compute_cash_gap_signal(
        _fj(deficit_day_14=base_date, deficit_day_14_stress=stress_date), AS_OF
    )
    assert result is not None
    assert result.is_stress is True
    assert result.days_until == 10
    assert result.severity == "critical"


def test_base_earlier_than_stress():
    base_date = (AS_OF + timedelta(days=5)).isoformat()
    stress_date = (AS_OF + timedelta(days=12)).isoformat()
    result = compute_cash_gap_signal(
        _fj(deficit_day_14=base_date, deficit_day_14_stress=stress_date), AS_OF
    )
    assert result is not None
    assert result.is_stress is False
    assert result.days_until == 5


def test_only_stress_present():
    stress_date = (AS_OF + timedelta(days=8)).isoformat()
    result = compute_cash_gap_signal(_fj(deficit_day_14_stress=stress_date), AS_OF)
    assert result is not None
    assert result.is_stress is True
    assert result.severity == "critical"


def test_cascades_to_next_horizon():
    """Если 14д нет, берёт 30д."""
    gap_date = (AS_OF + timedelta(days=25)).isoformat()
    result = compute_cash_gap_signal(_fj(deficit_day_30=gap_date), AS_OF)
    assert result is not None
    assert result.severity == "warning"


def test_past_date_skipped():
    """Разрыв в прошлом игнорируется."""
    past_date = (AS_OF - timedelta(days=1)).isoformat()
    result = compute_cash_gap_signal(_fj(deficit_day_14=past_date), AS_OF)
    assert result is None
