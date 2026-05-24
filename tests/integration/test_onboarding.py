"""
Integration tests: onboarding wizard API.
"""
import pytest

from .conftest import _register, auth_headers, FIXTURES_DIR

pytestmark = pytest.mark.asyncio


async def test_onboarding_status_new_company(client):
    user = await _register(client, company="OnbNewCo")
    resp = await client.get("/onboarding/status", headers=auth_headers(user["token"]))
    assert resp.status_code == 200
    data = resp.json()
    assert data["show_wizard"] is True
    assert data["current_step"] == "bank"
    bank = next(s for s in data["steps"] if s["id"] == "bank")
    assert bank["done"] is False
    assert bank["required"] is True


async def test_onboarding_dismiss_without_bank_fails(client):
    user = await _register(client, company="OnbNoBankCo")
    resp = await client.post("/onboarding/dismiss", headers=auth_headers(user["token"]))
    assert resp.status_code == 422


async def test_onboarding_after_bank_import_step_onec(client):
    user = await _register(client, company="OnbBankCo")
    headers = auth_headers(user["token"])
    csv_path = f"{FIXTURES_DIR}/sber_sample.csv"
    with open(csv_path, "rb") as f:
        r = await client.post(
            "/imports/bank",
            headers=headers,
            files={"file": ("sber_sample.csv", f, "text/csv")},
            data={"bank_key": "sber"},
        )
    assert r.status_code == 201

    resp = await client.get("/onboarding/status", headers=headers)
    data = resp.json()
    assert data["current_step"] == "onec"
    assert data["show_wizard"] is True
    bank = next(s for s in data["steps"] if s["id"] == "bank")
    assert bank["done"] is True


async def test_onboarding_dismiss_after_bank(client):
    user = await _register(client, company="OnbDismissCo")
    headers = auth_headers(user["token"])
    csv_path = f"{FIXTURES_DIR}/sber_sample.csv"
    with open(csv_path, "rb") as f:
        await client.post(
            "/imports/bank",
            headers=headers,
            files={"file": ("sber_sample.csv", f, "text/csv")},
            data={"bank_key": "sber"},
        )

    resp = await client.post("/onboarding/dismiss", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["dismissed"] is True
    assert data["show_wizard"] is False


async def test_onboarding_skip_onec(client):
    user = await _register(client, company="OnbSkipCo")
    headers = auth_headers(user["token"])
    csv_path = f"{FIXTURES_DIR}/sber_sample.csv"
    with open(csv_path, "rb") as f:
        await client.post(
            "/imports/bank",
            headers=headers,
            files={"file": ("sber_sample.csv", f, "text/csv")},
            data={"bank_key": "sber"},
        )

    resp = await client.post(
        "/onboarding/skip",
        headers=headers,
        json={"step": "onec"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_step"] == "telegram"
    onec = next(s for s in data["steps"] if s["id"] == "onec")
    assert onec["skipped"] is True


async def test_auth_me_telegram_connected(client):
    user = await _register(client, company="MeTelegramCo")
    resp = await client.get("/auth/me", headers=auth_headers(user["token"]))
    assert resp.status_code == 200
    assert resp.json()["telegram_connected"] is False
