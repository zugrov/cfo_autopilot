"""
RBAC — проверка прав доступа по ролям.

Роли: owner | accountant | viewer
Права:
  owner:      все операции
  accountant: чтение + загрузка + создание обязательств
  viewer:     только чтение
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.auth import get_current_user
from app.models import User

ROLE_HIERARCHY = {"owner": 3, "accountant": 2, "viewer": 1}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "owner": {"read", "import", "create_obligation", "manage_users", "admin"},
    "accountant": {"read", "import", "create_obligation"},
    "viewer": {"read"},
}


def require_permission(permission: str):
    """Dependency-фабрика для проверки прав доступа."""

    def _check(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        allowed = ROLE_PERMISSIONS.get(current_user.role, set())
        if permission not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' lacks permission '{permission}'",
            )
        return current_user

    return _check


def require_role(min_role: str):
    """Dependency: требует роль не ниже указанной."""

    def _check(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        user_level = ROLE_HIERARCHY.get(current_user.role, 0)
        required_level = ROLE_HIERARCHY.get(min_role, 99)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {min_role}, current: {current_user.role}",
            )
        return current_user

    return _check


ReadUser = Annotated[User, Depends(require_permission("read"))]
ImportUser = Annotated[User, Depends(require_permission("import"))]
ObligationUser = Annotated[User, Depends(require_permission("create_obligation"))]
OwnerUser = Annotated[User, Depends(require_role("owner"))]
