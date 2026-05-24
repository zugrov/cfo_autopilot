"""
Router: /auth — регистрация и вход.
"""
from __future__ import annotations

import random
import uuid

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel, EmailStr

from app.core.database import get_db
from app.core.auth import create_access_token, CurrentUser
from app.core.rbac import ReadUser, OwnerUser

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


class MeResponse(BaseModel):
    email: str
    role: str
    company_id: str
    telegram_connected: bool


@router.get("/me", response_model=MeResponse, summary="Текущий пользователь")
async def get_me(current_user: ReadUser) -> MeResponse:
    return MeResponse(
        email=current_user.email,
        role=current_user.role,
        company_id=str(current_user.company_id),
        telegram_connected=bool(current_user.telegram_chat_id),
    )


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
    current_user: OwnerUser,
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


CONNECT_CODE_TTL = 600  # 10 минут


@router.post("/me/telegram/connect-code", summary="Сгенерировать одноразовый код привязки Telegram")
async def generate_connect_code(current_user: OwnerUser) -> dict:
    """
    Генерирует 6-значный код и сохраняет его в Redis с TTL 10 минут.
    Бот использует этот код для команды /connect <code>.
    """
    from app.core.config import get_settings
    import redis.asyncio as aioredis

    settings = get_settings()
    code = f"{random.randint(0, 999999):06d}"
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis_client.set(f"connect:{code}", str(current_user.id), ex=CONNECT_CODE_TTL)
    finally:
        await redis_client.aclose()

    return {"code": code, "ttl_seconds": CONNECT_CODE_TTL}


class InternalSetTelegramRequest(BaseModel):
    user_id: str
    telegram_chat_id: str


@router.patch(
    "/internal/set-telegram",
    summary="[Internal] Привязать telegram_chat_id по user_id (вызывается ботом)",
    include_in_schema=False,
)
async def internal_set_telegram(
    body: InternalSetTelegramRequest,
    db: AsyncSession = Depends(get_db),
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
) -> dict:
    """
    Служебный endpoint: бот вызывает его после верификации кода из Redis.
    Защита через заголовок X-Internal-Secret (telegram_webhook_secret из .env).
    """
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.telegram_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal endpoint not configured",
        )
    if x_internal_secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    try:
        uid = uuid.UUID(body.user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user_id")

    # Получаем company_id пользователя для set_config RLS
    result = await db.execute(
        text('SELECT company_id FROM "user" WHERE id = :uid AND is_active = true'),
        {"uid": uid},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    company_id = row[0]
    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"),
        {"cid": str(company_id)},
    )
    await db.execute(
        text('UPDATE "user" SET telegram_chat_id = :tid WHERE id = :uid'),
        {"tid": body.telegram_chat_id, "uid": uid},
    )
    await db.commit()
    return {"status": "ok"}
