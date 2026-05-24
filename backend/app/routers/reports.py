"""
Router: /reports — управленческий дайджест PDF/email.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.database import get_db
from app.core.rbac import OwnerUser
from app.services.report.service import build_weekly_report_pdf, send_weekly_report_for_company

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/weekly", summary="Скачать еженедельный PDF-отчёт")
async def download_weekly_report(
    current_user: OwnerUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    cid = current_user.company_id
    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"),
        {"cid": str(cid)},
    )

    pdf_bytes, context, company_name = await build_weekly_report_pdf(db, cid)
    as_of_str = context.get("as_of", date.today().isoformat())[:10]

    await log_action(
        db,
        company_id=cid,
        user_id=current_user.id,
        action="weekly_report_sent",
        metadata={"channel": "download", "company_name": company_name},
    )
    await db.commit()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="report-{as_of_str}.pdf"',
        },
    )


@router.post("/weekly/send", summary="Отправить PDF-отчёт на email owner")
async def send_weekly_report(
    current_user: OwnerUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    cid = current_user.company_id
    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"),
        {"cid": str(cid)},
    )

    result = await send_weekly_report_for_company(db, cid)

    if result.get("sent"):
        await log_action(
            db,
            company_id=cid,
            user_id=current_user.id,
            action="weekly_report_sent",
            metadata={"channel": "email", "recipients": result.get("recipients", [])},
        )
        await db.commit()

    return result
