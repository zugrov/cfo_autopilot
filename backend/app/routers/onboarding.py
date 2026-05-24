"""
Router: /onboarding — guided-первый запуск.
"""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.database import get_db
from app.core.rbac import ImportUser, ReadUser
from app.services.onboarding.status import OnboardingFacts, compute_onboarding

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class SkipRequest(BaseModel):
    step: str


async def _load_facts(db: AsyncSession, company_id: uuid.UUID, user) -> OnboardingFacts:
    bank_row = await db.execute(
        text(
            "SELECT 1 FROM import_batch "
            "WHERE company_id = :cid AND source_type = 'bank_csv' "
            "  AND status IN ('done', 'partial') LIMIT 1"
        ),
        {"cid": company_id},
    )
    onec_row = await db.execute(
        text(
            "SELECT 1 FROM receivable "
            "WHERE company_id = :cid AND source = 'onec_osv' LIMIT 1"
        ),
        {"cid": company_id},
    )
    if onec_row.fetchone() is None:
        onec_batch = await db.execute(
            text(
                "SELECT 1 FROM import_batch "
                "WHERE company_id = :cid AND source_type = 'onec_file' "
                "  AND status IN ('done', 'partial') LIMIT 1"
            ),
            {"cid": company_id},
        )
        onec_done = onec_batch.fetchone() is not None
    else:
        onec_done = True

    settings_row = await db.execute(
        text("SELECT settings_json FROM company WHERE id = :cid"),
        {"cid": company_id},
    )
    settings = settings_row.scalar() or {}
    if isinstance(settings, str):
        settings = json.loads(settings)

    skipped = settings.get("onboarding_skipped") or {}
    return OnboardingFacts(
        bank_done=bank_row.fetchone() is not None,
        onec_done=onec_done,
        telegram_done=bool(user.telegram_chat_id),
        dismissed=bool(settings.get("onboarding_dismissed")),
        skipped_onec=bool(skipped.get("onec")),
        skipped_telegram=bool(skipped.get("telegram")),
        is_owner=user.role == "owner",
    )


async def _save_settings(
    db: AsyncSession,
    company_id: uuid.UUID,
    patch: dict,
) -> dict:
    row = await db.execute(
        text("SELECT settings_json FROM company WHERE id = :cid"),
        {"cid": company_id},
    )
    settings = row.scalar() or {}
    if isinstance(settings, str):
        settings = json.loads(settings)
    settings.update(patch)
    await db.execute(
        text("UPDATE company SET settings_json = CAST(:s AS jsonb) WHERE id = :cid"),
        {"s": json.dumps(settings), "cid": company_id},
    )
    return settings


@router.get("/status", summary="Статус onboarding")
async def onboarding_status(
    current_user: ReadUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    cid = current_user.company_id
    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"),
        {"cid": str(cid)},
    )
    facts = await _load_facts(db, cid, current_user)
    return compute_onboarding(facts)


@router.post("/dismiss", summary="Закрыть onboarding wizard")
async def dismiss_onboarding(
    current_user: ImportUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    cid = current_user.company_id
    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"),
        {"cid": str(cid)},
    )
    facts = await _load_facts(db, cid, current_user)
    if not facts.bank_done:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Сначала загрузите банковскую выписку",
        )
    await _save_settings(db, cid, {"onboarding_dismissed": True})
    await log_action(
        db,
        company_id=cid,
        user_id=current_user.id,
        action="onboarding_dismiss",
        entity="company",
        entity_id=cid,
    )
    await db.commit()
    facts.dismissed = True
    return compute_onboarding(facts)


@router.post("/skip", summary="Пропустить опциональный шаг onboarding")
async def skip_onboarding_step(
    body: SkipRequest,
    current_user: ImportUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if body.step not in ("onec", "telegram"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid step")
    if body.step == "telegram" and current_user.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Telegram step for owner only")

    cid = current_user.company_id
    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"),
        {"cid": str(cid)},
    )
    facts = await _load_facts(db, cid, current_user)
    if not facts.bank_done:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Сначала загрузите банковскую выписку",
        )

    skipped = {"onec": facts.skipped_onec, "telegram": facts.skipped_telegram}
    skipped[body.step] = True
    await _save_settings(db, cid, {"onboarding_skipped": skipped})
    await log_action(
        db,
        company_id=cid,
        user_id=current_user.id,
        action="onboarding_skip",
        entity="company",
        entity_id=cid,
        metadata={"step": body.step},
    )
    await db.commit()

    facts = await _load_facts(db, cid, current_user)
    return compute_onboarding(facts)
