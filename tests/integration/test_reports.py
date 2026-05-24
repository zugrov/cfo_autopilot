"""
Integration tests: /reports weekly PDF.
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
    user = await _register(client, company=f"Report Co {role}")
    await _set_user_role(user["user_id"], role)
    return user


async def test_owner_can_download_weekly_report(client):
    user = await _register_with_role(client, "owner")
    resp = await client.get("/reports/weekly", headers=auth_headers(user["token"]))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


async def test_viewer_cannot_download_weekly_report(client):
    user = await _register_with_role(client, "viewer")
    resp = await client.get("/reports/weekly", headers=auth_headers(user["token"]))
    assert resp.status_code == 403


async def test_owner_can_trigger_email_send(client):
    user = await _register_with_role(client, "owner")
    resp = await client.post(
        "/reports/weekly/send",
        headers=auth_headers(user["token"]),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "sent" in data
    assert data["company_id"] == user["company_id"]
