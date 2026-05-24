"""
Pilot smoke — полный happy-path MVP через API.
"""
from __future__ import annotations

import os
import uuid

import pytest

from .conftest import FIXTURES_DIR, _register, auth_headers

pytestmark = pytest.mark.asyncio

OBLIGATION_DUE = "2026-12-01"


async def test_pilot_happy_path(client):
    """Register → import → dashboard → obligations → team → audit → PDF."""
    user = await _register(client, company=f"Pilot Smoke {uuid.uuid4().hex[:6]}")
    token = user["token"]
    headers = auth_headers(token)
    csv_path = f"{FIXTURES_DIR}/sber_sample.csv"

    with open(csv_path, "rb") as f:
        import_resp = await client.post(
            "/imports/bank",
            headers=headers,
            files={"file": ("sber_sample.csv", f, "text/csv")},
            data={"bank_key": "sber"},
        )
    assert import_resp.status_code == 201, import_resp.text

    dash_resp = await client.get("/dashboard/today", headers=headers)
    assert dash_resp.status_code == 200
    dash = dash_resp.json()
    assert dash["has_data"] is True
    assert dash["balance"] is not None
    assert len(dash["forecast"]["days_preview"]) >= 90

    create_ob = await client.post(
        "/obligations",
        headers=headers,
        json={
            "due_date": OBLIGATION_DUE,
            "amount": 150_000,
            "description": "Pilot smoke — аренда",
        },
    )
    assert create_ob.status_code == 201, create_ob.text

    list_ob = await client.get("/obligations", headers=headers)
    assert list_ob.status_code == 200
    descriptions = [o["description"] for o in list_ob.json()["obligations"]]
    assert "Pilot smoke — аренда" in descriptions

    invite_email = f"viewer_{uuid.uuid4().hex[:6]}@example.com"
    invite_resp = await client.post(
        "/users",
        headers=headers,
        json={"email": invite_email, "role": "viewer"},
    )
    assert invite_resp.status_code == 201, invite_resp.text

    audit_resp = await client.get("/audit?limit=20", headers=headers)
    assert audit_resp.status_code == 200
    actions = [e["action"] for e in audit_resp.json()["entries"]]
    assert "invite_user" in actions

    pdf_resp = await client.get("/reports/weekly", headers=headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content[:4] == b"%PDF"


@pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY не задан — AI smoke пропущен",
)
async def test_pilot_ai_chat(client):
    """AI-чат после импорта (требует LLM-ключ)."""
    user = await _register(client, company=f"Pilot AI {uuid.uuid4().hex[:6]}")
    headers = auth_headers(user["token"])
    csv_path = f"{FIXTURES_DIR}/sber_sample.csv"

    with open(csv_path, "rb") as f:
        await client.post(
            "/imports/bank",
            headers=headers,
            files={"file": ("sber_sample.csv", f, "text/csv")},
            data={"bank_key": "sber"},
        )

    chat_resp = await client.post(
        "/ai/chat",
        headers=headers,
        json={"question": "Какой прогноз остатка на неделю?"},
    )
    assert chat_resp.status_code == 200, chat_resp.text
    data = chat_resp.json()
    assert data.get("answer")
    assert data.get("provider")
