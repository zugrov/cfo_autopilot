"""Tests for PDF generation."""
from app.services.report.pdf import render_weekly_pdf


def _sample_context() -> dict:
    return {
        "has_data": True,
        "as_of": "2026-05-24",
        "balance": 1_500_000,
        "forecast": {
            "deficit_signal": {
                "date": "2026-06-10",
                "is_stress": False,
                "days_until": 17,
                "severity": "warning",
            },
            "days_stress": [],
        },
        "obligations": [
            {
                "due_date": "2026-05-30",
                "amount": 200_000,
                "description": "Аренда",
                "days_until": 6,
            }
        ],
        "explain": {
            "headline": "Остаток снизился на ₽ 50 000 за 7 дней",
            "reasons": [
                {"type": "debit", "label": "Аренда", "amount": 200_000, "date": "2026-05-20"}
            ],
        },
        "receivables": None,
        "reconciliation": None,
        "stale": {"is_stale": False, "hours": None},
        "last_import_at": "2026-05-24T10:00:00",
    }


def test_render_weekly_pdf_returns_valid_pdf():
    pdf_bytes = render_weekly_pdf(_sample_context(), "Тестовая компания")
    assert len(pdf_bytes) > 500
    assert pdf_bytes[:4] == b"%PDF"


def test_render_weekly_pdf_no_data():
    context = {
        "has_data": False,
        "as_of": "2026-05-24",
        "obligations": [],
        "stale": {"is_stale": True, "hours": 30},
        "last_import_at": None,
    }
    pdf_bytes = render_weekly_pdf(context, "Пустая компания")
    assert pdf_bytes[:4] == b"%PDF"
