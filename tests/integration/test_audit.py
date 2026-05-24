"""
Integration tests: /audit journal.
"""
import uuid

import pytest
from sqlalchemy import text

from .conftest import _register, auth_headers

pytestmark = pytest.mark.asyncio


async def _set_user_role(user_id: str, role: str) -> None:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(
            text('UPDATE "user" SET role = :role WHERE id = :uid'),
            {"role": role, "uid": uuid.UUID(user_id)},
        )
        await db.commit()


async def _register_with_role(client, role: str) -> dict:
    user = await _register(client, company=f"Audit Co {role}")
    await _set_user_role(user["user_id"], role)
    return user


async def test_owner_can_list_audit_log(client):
    user = await _register_with_role(client, "owner")
    resp = await client.get("/audit", headers=auth_headers(user["token"]))
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert "total" in data
    assert isinstance(data["entries"], list)


async def test_viewer_cannot_list_audit_log(client):
    user = await _register_with_role(client, "viewer")
    resp = await client.get("/audit", headers=auth_headers(user["token"]))
    assert resp.status_code == 403


async def test_audit_log_after_invite(client):
    owner = await _register_with_role(client, "owner")
    invite_resp = await client.post(
        "/users",
        headers=auth_headers(owner["token"]),
        json={"email": f"invited_{uuid.uuid4().hex[:6]}@example.com", "role": "viewer"},
    )
    assert invite_resp.status_code == 201

    audit_resp = await client.get("/audit", headers=auth_headers(owner["token"]))
    assert audit_resp.status_code == 200
    actions = [e["action"] for e in audit_resp.json()["entries"]]
    assert "invite_user" in actions
