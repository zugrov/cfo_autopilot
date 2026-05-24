"""
Integration tests: управление командой (/users).
"""
import uuid

import pytest
from sqlalchemy import text

from .conftest import _register, auth_headers, FIXTURES_DIR

pytestmark = pytest.mark.asyncio


async def _set_user_role(user_id: str, role: str) -> None:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(
            text('UPDATE "user" SET role = :role WHERE id = :uid'),
            {"role": role, "uid": uuid.UUID(user_id)},
        )
        await db.commit()


async def _login(client, email: str) -> str:
    resp = await client.post("/auth/login", json={"email": email})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def test_owner_invites_viewer(client):
    owner = await _register(client, company="TeamOwnerCo")
    owner_headers = auth_headers(owner["token"])

    resp = await client.post(
        "/users",
        headers=owner_headers,
        json={"email": "viewer@teamco.ru", "role": "viewer"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["role"] == "viewer"

    viewer_token = await _login(client, "viewer@teamco.ru")
    viewer_headers = auth_headers(viewer_token)

    dash = await client.get("/dashboard/today", headers=viewer_headers)
    assert dash.status_code == 200

    csv_path = f"{FIXTURES_DIR}/sber_sample.csv"
    with open(csv_path, "rb") as f:
        imp = await client.post(
            "/imports/bank",
            headers=viewer_headers,
            files={"file": ("sber_sample.csv", f, "text/csv")},
            data={"bank_key": "sber"},
        )
    assert imp.status_code == 403


async def test_owner_invites_accountant_can_import(client):
    owner = await _register(client, company="TeamAcctCo")
    owner_headers = auth_headers(owner["token"])

    resp = await client.post(
        "/users",
        headers=owner_headers,
        json={"email": "acct@teamco.ru", "role": "accountant"},
    )
    assert resp.status_code == 201

    acct_token = await _login(client, "acct@teamco.ru")
    acct_headers = auth_headers(acct_token)

    csv_path = f"{FIXTURES_DIR}/sber_sample.csv"
    with open(csv_path, "rb") as f:
        imp = await client.post(
            "/imports/bank",
            headers=acct_headers,
            files={"file": ("sber_sample.csv", f, "text/csv")},
            data={"bank_key": "sber"},
        )
    assert imp.status_code == 201, imp.text


async def test_accountant_cannot_invite(client):
    owner = await _register(client, company="TeamNoInviteCo")
    await _set_user_role(owner["user_id"], "accountant")
    acct_token = await _login(client, owner["email"])

    resp = await client.post(
        "/users",
        headers=auth_headers(acct_token),
        json={"email": "new@teamco.ru", "role": "viewer"},
    )
    assert resp.status_code == 403


async def test_duplicate_email_on_invite(client):
    owner = await _register(client, company="TeamDupCo")
    owner_headers = auth_headers(owner["token"])

    await client.post(
        "/users",
        headers=owner_headers,
        json={"email": "dup@teamco.ru", "role": "viewer"},
    )
    resp = await client.post(
        "/users",
        headers=owner_headers,
        json={"email": "dup@teamco.ru", "role": "accountant"},
    )
    assert resp.status_code == 409


async def test_owner_deactivates_viewer(client):
    owner = await _register(client, company="TeamDeactCo")
    owner_headers = auth_headers(owner["token"])

    invite = await client.post(
        "/users",
        headers=owner_headers,
        json={"email": "gone@teamco.ru", "role": "viewer"},
    )
    viewer_id = invite.json()["id"]

    patch = await client.patch(
        f"/users/{viewer_id}",
        headers=owner_headers,
        json={"is_active": False},
    )
    assert patch.status_code == 200

    login = await client.post("/auth/login", json={"email": "gone@teamco.ru"})
    assert login.status_code == 401


async def test_list_users(client):
    owner = await _register(client, company="TeamListCo")
    owner_headers = auth_headers(owner["token"])

    await client.post(
        "/users",
        headers=owner_headers,
        json={"email": "member@teamco.ru", "role": "viewer"},
    )

    resp = await client.get("/users", headers=owner_headers)
    assert resp.status_code == 200
    users = resp.json()["users"]
    assert len(users) == 2
    emails = {u["email"] for u in users}
    assert "member@teamco.ru" in emails
