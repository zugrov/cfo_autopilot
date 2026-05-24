"""Tests for email builder and SMTP helper."""
from unittest.mock import AsyncMock, patch

import pytest

from app.services.report.email import (
    build_weekly_email_html,
    is_smtp_configured,
    send_weekly_email,
)


def test_build_weekly_email_html_contains_company():
    context = {
        "has_data": True,
        "as_of": "2026-05-24",
        "balance": 1_000_000,
        "explain": {"headline": "Остаток вырос"},
        "forecast": {},
        "stale": {"is_stale": False},
    }
    html = build_weekly_email_html(context, "ООО Ромашка")
    assert "ООО Ромашка" in html
    assert "1 000 000" in html or "1000000" in html.replace(",", " ")


def test_is_smtp_configured_false_by_default():
    assert is_smtp_configured() is False


@pytest.mark.asyncio
async def test_send_weekly_email_skips_without_smtp():
    result = await send_weekly_email(
        ["owner@test.com"],
        b"%PDF",
        "<html></html>",
        "Test",
    )
    assert result is False


@pytest.mark.asyncio
async def test_send_weekly_email_success():
    with patch("app.services.report.email.get_settings") as mock_settings:
        mock_settings.return_value.smtp_host = "smtp.test.com"
        mock_settings.return_value.smtp_from = "noreply@test.com"
        mock_settings.return_value.smtp_port = 587
        mock_settings.return_value.smtp_user = "user"
        mock_settings.return_value.smtp_password = "pass"
        mock_settings.return_value.smtp_use_tls = True

        with patch("app.services.report.email.aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            result = await send_weekly_email(
                ["owner@test.com"],
                b"%PDF-1.4 test",
                "<html><body>Hi</body></html>",
                "Weekly report",
            )
            assert result is True
            mock_send.assert_called_once()
