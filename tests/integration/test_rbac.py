"""
Integration tests: RBAC на роутах.
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


async def _register_with_role(client, role: str, company: str = "RBAC Co") -> dict:
    user = await _register(client, company=company)
    await _set_user_role(user["user_id"], role)
    return user


async def test_viewer_can_read_dashboard(client):
    user = await _register_with_role(client, "viewer")
    resp = await client.get("/dashboard/today", headers=auth_headers(user["token"]))
    assert resp.status_code == 200


async def test_viewer_cannot_import_bank(client):
    user = await _register_with_role(client, "viewer")
    csv_path = f"{FIXTURES_DIR}/sber_sample.csv"
    with open(csv_path, "rb") as f:
        resp = await client.post(
            "/imports/bank",
            headers=auth_headers(user["token"]),
            files={"file": ("sber_sample.csv", f, "text/csv")},
            data={"bank_key": "sber"},
        )
    assert resp.status_code == 403


async def test_viewer_cannot_create_obligation(client):
    user = await _register_with_role(client, "viewer")
    resp = await client.post(
        "/obligations",
        headers=auth_headers(user["token"]),
        json={
            "due_date": "2026-06-01",
            "amount": 100000,
            "description": "Test",
        },
    )
    assert resp.status_code == 403


async def test_accountant_can_import_bank(client):
    user = await _register_with_role(client, "accountant")
    csv_path = f"{FIXTURES_DIR}/sber_sample.csv"
    with open(csv_path, "rb") as f:
        resp = await client.post(
            "/imports/bank",
            headers=auth_headers(user["token"]),
            files={"file": ("sber_sample.csv", f, "text/csv")},
            data={"bank_key": "sber"},
        )
    assert resp.status_code == 201, resp.text


async def test_auth_me_returns_role(client):
    user = await _register_with_role(client, "accountant")
    resp = await client.get("/auth/me", headers=auth_headers(user["token"]))
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "accountant"
    assert data["email"]
