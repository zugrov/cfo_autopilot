import uuid
from typing import Optional
from fastapi import Request, HTTPException, status
from jose import jwt, JWTError

from app.core.config import get_settings

settings = get_settings()

BEARER_PREFIX = "Bearer "


def _extract_token(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.startswith(BEARER_PREFIX):
        return auth[len(BEARER_PREFIX):]
    return None


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


class TenantMiddleware:
    """Устанавливает app.company_id для PostgreSQL RLS из JWT."""

    async def __call__(self, request: Request, call_next):
        token = _extract_token(request)
        if token:
            try:
                payload = decode_token(token)
                company_id = payload.get("company_id")
                if company_id:
                    request.state.company_id = str(company_id)
                    request.state.user_id = payload.get("sub")
            except HTTPException:
                pass

        response = await call_next(request)
        return response
