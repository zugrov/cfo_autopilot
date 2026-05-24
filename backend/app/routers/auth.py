"""
Router: /auth — регистрация и вход.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel, EmailStr

from app.core.database import get_db
from app.core.auth import create_access_token, CurrentUser

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    company_name: str


class LoginRequest(BaseModel):
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    company_id: str
    user_id: str


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """
    Создаёт компанию и пользователя (owner role).
    В production: интеграция с Supabase Auth для email-подтверждения.
    """
    # Проверка дубликата email
    existing = await db.execute(
        text('SELECT id FROM "user" WHERE email = :email'), {"email": body.email}
    )
    if existing.fetchone():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    company_id = uuid.uuid4()
    user_id = uuid.uuid4()

    await db.execute(
        text(
            "INSERT INTO company (id, name, timezone, settings_json, created_at) "
            "VALUES (:id, :name, 'Europe/Moscow', '{}', now())"
        ),
        {"id": company_id, "name": body.company_name},
    )
    await db.execute(
        text(
            'INSERT INTO "user" (id, company_id, email, role, is_active, created_at) '
            "VALUES (:id, :company_id, :email, 'owner', true, now())"
        ),
        {"id": user_id, "company_id": company_id, "email": body.email},
    )
    await db.commit()

    token = create_access_token(user_id=user_id, company_id=company_id, role="owner")
    return TokenResponse(
        access_token=token,
        company_id=str(company_id),
        user_id=str(user_id),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Упрощённый вход по email (MVP). Production: Supabase Auth OTP/password."""
    result = await db.execute(
        text('SELECT id, company_id, role FROM "user" WHERE email = :email AND is_active = true'),
        {"email": body.email},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    user_id, company_id, role = row
    token = create_access_token(user_id=user_id, company_id=company_id, role=role)
    return TokenResponse(
        access_token=token,
        company_id=str(company_id),
        user_id=str(user_id),
    )


class TelegramRequest(BaseModel):
    telegram_chat_id: str


@router.patch("/me/telegram", summary="Привязать Telegram chat_id к аккаунту")
async def set_telegram(
    body: TelegramRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Сохраняет telegram_chat_id пользователя — после этого бот начнёт присылать дайджест."""
    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"),
        {"cid": str(current_user.company_id)},
    )
    await db.execute(
        text('UPDATE "user" SET telegram_chat_id = :tid WHERE id = :uid'),
        {"tid": body.telegram_chat_id, "uid": current_user.id},
    )
    await db.commit()
    return {"status": "ok", "telegram_chat_id": body.telegram_chat_id}
