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
    viewer_email = f"viewer_{uuid.uuid4().hex[:8]}@example.com"

    resp = await client.post(
        "/users",
        headers=owner_headers,
        json={"email": viewer_email, "role": "viewer"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["role"] == "viewer"

    viewer_token = await _login(client, viewer_email)
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
    acct_email = f"acct_{uuid.uuid4().hex[:8]}@example.com"

    resp = await client.post(
        "/users",
        headers=owner_headers,
        json={"email": acct_email, "role": "accountant"},
    )
    assert resp.status_code == 201

    acct_token = await _login(client, acct_email)
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
    new_email = f"new_{uuid.uuid4().hex[:8]}@example.com"

    resp = await client.post(
        "/users",
        headers=auth_headers(acct_token),
        json={"email": new_email, "role": "viewer"},
    )
    assert resp.status_code == 403


async def test_duplicate_email_on_invite(client):
    owner = await _register(client, company="TeamDupCo")
    owner_headers = auth_headers(owner["token"])
    dup_email = f"dup_{uuid.uuid4().hex[:8]}@example.com"

    await client.post(
        "/users",
        headers=owner_headers,
        json={"email": dup_email, "role": "viewer"},
    )
    resp = await client.post(
        "/users",
        headers=owner_headers,
        json={"email": dup_email, "role": "accountant"},
    )
    assert resp.status_code == 409


async def test_owner_deactivates_viewer(client):
    owner = await _register(client, company="TeamDeactCo")
    owner_headers = auth_headers(owner["token"])
    gone_email = f"gone_{uuid.uuid4().hex[:8]}@example.com"

    invite = await client.post(
        "/users",
        headers=owner_headers,
        json={"email": gone_email, "role": "viewer"},
    )
    assert invite.status_code == 201, invite.text
    viewer_id = invite.json()["id"]

    patch = await client.patch(
        f"/users/{viewer_id}",
        headers=owner_headers,
        json={"is_active": False},
    )
    assert patch.status_code == 200

    login = await client.post("/auth/login", json={"email": gone_email})
    assert login.status_code == 401


async def test_list_users(client):
    owner = await _register(client, company="TeamListCo")
    owner_headers = auth_headers(owner["token"])
    member_email = f"member_{uuid.uuid4().hex[:8]}@example.com"

    await client.post(
        "/users",
        headers=owner_headers,
        json={"email": member_email, "role": "viewer"},
    )

    resp = await client.get("/users", headers=owner_headers)
    assert resp.status_code == 200
    users = resp.json()["users"]
    assert len(users) == 2
    emails = {u["email"] for u in users}
    assert member_email in emails
