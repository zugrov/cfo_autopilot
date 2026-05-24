"""
Router: /ai — AI-чат (Sprint 3).
Structured query first, LLM second.
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

from app.core.database import get_db
from app.core.rbac import ReadUser
from app.services.llm.adapter import ask_llm, redact_pii

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    provider: str
    cached: bool


@router.post("/chat", response_model=ChatResponse, summary="AI-ответ на финансовый вопрос")
async def ai_chat(
    body: ChatRequest,
    current_user: ReadUser,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    cid = current_user.company_id
    today = date.today()

    if len(body.question) > 500:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Вопрос слишком длинный")

    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"), {"cid": str(cid)}
    )

    # Строим контекст из БД для RAG
    snap = await db.execute(
        text(
            "SELECT balance, forecast_json FROM daily_cash_snapshot "
            "WHERE company_id = :cid AND snapshot_date = :today"
        ),
        {"cid": cid, "today": today},
    )
    snap_row = snap.fetchone()

    obligations = await db.execute(
        text(
            "SELECT due_date, amount, description FROM obligation "
            "WHERE company_id = :cid AND status='pending' ORDER BY due_date LIMIT 5"
        ),
        {"cid": cid},
    )

    context_parts = []
    if snap_row:
        context_parts.append(f"Остаток сегодня: ₽{float(snap_row[0]):,.0f}".replace(",", " "))
        forecast = snap_row[1]
        if forecast.get("deficit_day_14"):
            context_parts.append(f"Кассовый разрыв ожидается: {forecast['deficit_day_14']}")

    for ob in obligations.fetchall():
        context_parts.append(
            f"Обязательство {ob[0].isoformat()}: ₽{float(ob[1]):,.0f} — {ob[2]}".replace(",", " ")
        )

    context = "\n".join(context_parts) if context_parts else "Данные не загружены"

    # data_version = max updated_at import_batch
    dv_row = await db.execute(
        text("SELECT MAX(updated_at) FROM import_batch WHERE company_id = :cid"),
        {"cid": cid},
    )
    data_version = str(dv_row.scalar() or "")

    # Настройка провайдера из company.settings_json
    pref_row = await db.execute(
        text("SELECT settings_json FROM company WHERE id = :cid"),
        {"cid": cid},
    )
    settings_json = pref_row.scalar() or {}
    preferred = settings_json.get("llm_provider", "openrouter")

    result = await ask_llm(
        question=body.question,
        context=context,
        data_version=data_version,
        preferred_provider=preferred,
    )

    return ChatResponse(
        answer=result["answer"],
        provider=result["provider"],
        cached=result["cached"],
    )
