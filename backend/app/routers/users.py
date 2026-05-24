"""
Router: /users — управление командой компании (manage_users).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.database import get_db
from app.core.rbac import ManageUser

router = APIRouter(prefix="/users", tags=["users"])

INVITE_ROLES = frozenset({"accountant", "viewer"})
PATCH_ROLES = frozenset({"accountant", "viewer"})


class InviteUserRequest(BaseModel):
    email: EmailStr
    role: str


class UpdateUserRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None


@router.get("", summary="Список пользователей компании")
async def list_users(
    current_user: ManageUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    cid = current_user.company_id
    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"),
        {"cid": str(cid)},
    )
    result = await db.execute(
        text(
            'SELECT id, email, role, is_active, created_at, telegram_chat_id '
            'FROM "user" WHERE company_id = :cid ORDER BY created_at'
        ),
        {"cid": cid},
    )
    rows = result.fetchall()
    return {
        "users": [
            {
                "id": str(r[0]),
                "email": r[1],
                "role": r[2],
                "is_active": r[3],
                "created_at": r[4].isoformat() if r[4] else None,
                "telegram_connected": bool(r[5]),
            }
            for r in rows
        ]
    }


@router.post("", status_code=status.HTTP_201_CREATED, summary="Пригласить пользователя")
async def invite_user(
    body: InviteUserRequest,
    current_user: ManageUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if body.role not in INVITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Role must be accountant or viewer",
        )

    cid = current_user.company_id
    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"),
        {"cid": str(cid)},
    )

    existing = await db.execute(
        text('SELECT id FROM "user" WHERE email = :email'),
        {"email": body.email},
    )
    if existing.fetchone():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    new_id = uuid.uuid4()
    await db.execute(
        text(
            'INSERT INTO "user" (id, company_id, email, role, is_active, created_at) '
            "VALUES (:id, :cid, :email, :role, true, now())"
        ),
        {"id": new_id, "cid": cid, "email": body.email, "role": body.role},
    )
    await log_action(
        db,
        company_id=cid,
        user_id=current_user.id,
        action="invite_user",
        entity="user",
        entity_id=new_id,
        metadata={"email": body.email, "role": body.role},
    )
    await db.commit()

    return {
        "id": str(new_id),
        "email": body.email,
        "role": body.role,
        "is_active": True,
    }


@router.patch("/{user_id}", summary="Обновить роль или статус пользователя")
async def update_user(
    user_id: uuid.UUID,
    body: UpdateUserRequest,
    current_user: ManageUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot modify yourself",
        )
    if body.role is None and body.is_active is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nothing to update",
        )
    if body.role is not None and body.role not in PATCH_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Role must be accountant or viewer",
        )

    cid = current_user.company_id
    await db.execute(
        text("SELECT set_config('app.company_id', :cid, true)"),
        {"cid": str(cid)},
    )

    target = await db.execute(
        text(
            'SELECT id, email, role, is_active FROM "user" '
            "WHERE id = :uid AND company_id = :cid"
        ),
        {"uid": user_id, "cid": cid},
    )
    row = target.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    _, email, current_role, current_active = row

    if current_role == "owner":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot modify owner",
        )

    new_active = body.is_active if body.is_active is not None else current_active
    new_role = body.role if body.role is not None else current_role

    if body.is_active is False or (body.role is not None and new_active is False):
        pass  # deactivation allowed for non-owners

    if body.role is not None:
        await db.execute(
            text('UPDATE "user" SET role = :role WHERE id = :uid'),
            {"role": new_role, "uid": user_id},
        )
    if body.is_active is not None:
        await db.execute(
            text('UPDATE "user" SET is_active = :active WHERE id = :uid'),
            {"active": body.is_active, "uid": user_id},
        )

    await log_action(
        db,
        company_id=cid,
        user_id=current_user.id,
        action="update_user",
        entity="user",
        entity_id=user_id,
        metadata={"email": email, "role": new_role, "is_active": new_active},
    )
    await db.commit()

    return {
        "id": str(user_id),
        "email": email,
        "role": new_role,
        "is_active": new_active,
    }
