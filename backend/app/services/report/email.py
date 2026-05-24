"""
Email-рассылка еженедельного управленческого отчёта.
"""
from __future__ import annotations

import logging
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.core.config import get_settings
from app.services.report.actions import build_recommended_actions

logger = logging.getLogger(__name__)


def _money(amount: float | None) -> str:
    if amount is None:
        return "—"
    return f"₽ {amount:,.0f}".replace(",", " ")


def build_weekly_email_html(context: dict, company_name: str) -> str:
    """Краткое HTML-письмо с резюме отчёта."""
    as_of = context.get("as_of", "")[:10]
    balance = _money(context.get("balance")) if context.get("has_data") else "нет данных"
    explain = (context.get("explain") or {}).get("headline", "")
    forecast = context.get("forecast") or {}
    signal = forecast.get("deficit_signal")
    gap_line = ""
    if signal:
        gap_line = (
            f"<p>Риск кассового разрыва через {signal.get('days_until')} дн. "
            f"({signal.get('date', '')[:10]})</p>"
        )

    actions = build_recommended_actions(context)
    action_html = "".join(f"<li>{a}</li>" for a in actions[:3])

    return f"""
<html>
<body style="font-family: sans-serif; color: #333;">
  <h2>Управленческий дайджест — {company_name}</h2>
  <p>Неделя по {_format_date(as_of)}</p>
  <p><strong>Остаток:</strong> {balance}</p>
  {f'<p>{explain}</p>' if explain else ''}
  {gap_line}
  <p><strong>Рекомендации:</strong></p>
  <ul>{action_html}</ul>
  <p style="color:#888;font-size:12px;">
    Полный отчёт — во вложении PDF. Открыть детали → личный кабинет.
  </p>
</body>
</html>
"""


def _format_date(iso: str) -> str:
    if not iso:
        return "—"
    parts = iso[:10].split("-")
    if len(parts) == 3:
        return f"{parts[2]}.{parts[1]}.{parts[0]}"
    return iso


def is_smtp_configured() -> bool:
    settings = get_settings()
    return bool(settings.smtp_host and settings.smtp_from)


async def send_weekly_email(
    to: list[str],
    pdf_bytes: bytes,
    html: str,
    subject: str,
    *,
    filename: str = "weekly-report.pdf",
) -> bool:
    """
    Отправляет письмо с PDF-вложением.
    Возвращает True при успехе, False если SMTP не настроен или ошибка.
    """
    if not to:
        return False

    settings = get_settings()
    if not is_smtp_configured():
        logger.warning("SMTP не настроен — email-отчёт пропущен")
        return False

    msg = MIMEMultipart()
    msg["From"] = settings.smtp_from
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html", "utf-8"))

    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(attachment)

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            start_tls=settings.smtp_use_tls,
        )
        return True
    except Exception as exc:
        logger.error("Ошибка отправки email: %s", exc)
        return False
