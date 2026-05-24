"""
Unit-тесты: RBAC permissions.
"""
import uuid

import pytest
from fastapi import HTTPException

from app.core.rbac import (
    ROLE_PERMISSIONS,
    require_permission,
    require_role,
)
from app.models import User


def _user(role: str) -> User:
    return User(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        email="test@example.com",
        role=role,
        is_active=True,
    )


class TestRolePermissions:
    def test_viewer_read_only(self):
        perms = ROLE_PERMISSIONS["viewer"]
        assert "read" in perms
        assert "import" not in perms
        assert "create_obligation" not in perms

    def test_accountant_can_import_and_obligations(self):
        perms = ROLE_PERMISSIONS["accountant"]
        assert "import" in perms
        assert "create_obligation" in perms
        assert "manage_users" not in perms

    def test_owner_has_all_permissions(self):
        perms = ROLE_PERMISSIONS["owner"]
        assert "manage_users" in perms
        assert "admin" in perms


class TestRequirePermission:
    def test_viewer_denied_import(self):
        check = require_permission("import")
        with pytest.raises(HTTPException) as exc:
            check(_user("viewer"))
        assert exc.value.status_code == 403

    def test_viewer_denied_create_obligation(self):
        check = require_permission("create_obligation")
        with pytest.raises(HTTPException) as exc:
            check(_user("viewer"))
        assert exc.value.status_code == 403

    def test_accountant_allowed_import(self):
        check = require_permission("import")
        result = check(_user("accountant"))
        assert result.role == "accountant"

    def test_accountant_denied_manage_users(self):
        check = require_permission("manage_users")
        with pytest.raises(HTTPException) as exc:
            check(_user("accountant"))
        assert exc.value.status_code == 403


class TestRequireRole:
    def test_viewer_not_owner(self):
        check = require_role("owner")
        with pytest.raises(HTTPException) as exc:
            check(_user("viewer"))
        assert exc.value.status_code == 403

    def test_owner_passes(self):
        check = require_role("owner")
        assert check(_user("owner")).role == "owner"
