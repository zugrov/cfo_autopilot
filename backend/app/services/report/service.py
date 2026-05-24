"""
Сервис отправки еженедельного отчёта — общая логика для API и ARQ.
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.report.context import build_report_context, get_company_name
from app.services.report.email import build_weekly_email_html, send_weekly_email
from app.services.report.pdf import render_weekly_pdf


async def is_weekly_report_enabled(db: AsyncSession, company_id: uuid.UUID) -> bool:
    row = await db.execute(
        text("SELECT settings_json FROM company WHERE id = :cid"),
        {"cid": company_id},
    )
    settings = row.scalar() or {}
    return settings.get("weekly_report_enabled", True)


async def get_owner_emails(db: AsyncSession, company_id: uuid.UUID) -> list[str]:
    result = await db.execute(
        text(
            'SELECT email FROM "user" '
            "WHERE company_id = :cid AND role = 'owner' AND is_active = true"
        ),
        {"cid": company_id},
    )
    return [r[0] for r in result.fetchall()]


async def build_weekly_report_pdf(
    db: AsyncSession,
    company_id: uuid.UUID,
    as_of: date | None = None,
) -> tuple[bytes, dict, str]:
    """Собирает context, рендерит PDF. Возвращает (pdf_bytes, context, company_name)."""
    report_date = as_of or date.today()
    context = await build_report_context(
        db, company_id, report_date, obligations_limit=5
    )
    company_name = await get_company_name(db, company_id)
    pdf_bytes = render_weekly_pdf(context, company_name)
    return pdf_bytes, context, company_name


async def send_weekly_report_for_company(
    db: AsyncSession,
    company_id: uuid.UUID,
    as_of: date | None = None,
) -> dict:
    """Отправляет PDF на email всех owner компании."""
    if not await is_weekly_report_enabled(db, company_id):
        return {"sent": False, "reason": "disabled", "company_id": str(company_id)}

    recipients = await get_owner_emails(db, company_id)
    if not recipients:
        return {"sent": False, "reason": "no_recipients", "company_id": str(company_id)}

    pdf_bytes, context, company_name = await build_weekly_report_pdf(db, company_id, as_of)
    as_of_str = context.get("as_of", date.today().isoformat())[:10]
    subject = f"Управленческий дайджест — {company_name} ({as_of_str})"
    html = build_weekly_email_html(context, company_name)
    filename = f"report-{as_of_str}.pdf"

    ok = await send_weekly_email(
        recipients,
        pdf_bytes,
        html,
        subject,
        filename=filename,
    )
    return {
        "sent": ok,
        "recipients": recipients if ok else [],
        "company_id": str(company_id),
    }
