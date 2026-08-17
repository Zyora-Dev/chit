from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.company import Company
from app.models.user import User


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_company_onboarding_and_logo_upload(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    email = "company-owner@example.com"
    welcome_sends = []

    async def fake_platform_settings(db):
        return object()

    async def fake_welcome_send(config, *, recipient, template_name, language_code):
        welcome_sends.append((recipient, template_name, language_code))
        return {"messages": [{"id": "wamid.test-welcome", "message_status": "accepted"}]}

    monkeypatch.setattr("app.api.routes.companies.get_platform_whatsapp_settings", fake_platform_settings)
    monkeypatch.setattr("app.api.routes.companies.send_whatsapp_template", fake_welcome_send)
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password("StrongPassword123!"),
                role="owner",
                is_verified=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        existing_company = await db.scalar(select(Company).where(Company.owner_id == user.id))
        if existing_company:
            await db.delete(existing_company)
            await db.commit()
        user_id = user.id
        token = create_access_token(user.id, user.role)

    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "name": "zChit Test Company",
        "legal_name": "zChit Test Company Private Limited",
        "mobile_number": "+919876543210",
        "email": "company@example.com",
        "gstin": "33ABCDE1234F1Z5",
        "pan": "ABCDE1234F",
        "website": "https://example.com",
        "addresses": [
            {
                "address_type": "registered",
                "is_primary": True,
                "address_line_1": "10 Test Street",
                "locality": "Test Nagar",
                "city": "Nagercoil",
                "state": "Tamil Nadu",
                "postal_code": "629001",
                "country": "India",
            },
            {
                "address_type": "branch",
                "address_line_1": "20 Branch Road",
                "city": "Chennai",
                "state": "Tamil Nadu",
                "postal_code": "600001",
                "country": "India",
            },
        ],
    }

    try:
        response = await client.post("/api/v1/companies", json=payload, headers=headers)
        assert response.status_code == 201, response.text
        company = response.json()
        assert company["company_code"].startswith("ZCH-")
        assert len(company["addresses"]) == 2
        assert sum(address["is_primary"] for address in company["addresses"]) == 1
        assert welcome_sends == [(payload["mobile_number"], "welcome", "en")]
        async with AsyncSessionLocal() as db:
            saved_company = await db.scalar(select(Company).where(Company.id == company["id"]))
            assert saved_company.welcome_whatsapp_sent_at is not None

        response = await client.get("/api/v1/companies/me", headers=headers)
        assert response.status_code == 200
        assert response.json()["company_code"] == company["company_code"]

        updated_payload = {
            **payload,
            "name": "Updated zChit Company",
            "addresses": [{
                **payload["addresses"][0],
                "address_line_1": "25 Updated Street",
            }],
        }
        response = await client.put(
            "/api/v1/companies/me", json=updated_payload, headers=headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["name"] == "Updated zChit Company"
        assert response.json()["addresses"][0]["address_line_1"] == "25 Updated Street"

        png = b"\x89PNG\r\n\x1a\n" + b"test-image-content"
        response = await client.post(
            "/api/v1/companies/me/logo",
            headers=headers,
            files={"logo": ("logo.png", png, "image/png")},
        )
        assert response.status_code == 200, response.text
        logo_url = response.json()["logo_url"]
        assert logo_url.endswith("/logo.png")
        assert Path(settings.upload_directory, logo_url.removeprefix("/uploads/")).exists()

        duplicate = await client.post("/api/v1/companies", json=payload, headers=headers)
        assert duplicate.status_code == 409
    finally:
        async with AsyncSessionLocal() as db:
            company = await db.scalar(select(Company).where(Company.owner_id == user_id))
            if company:
                company_directory = Path(settings.upload_directory) / "companies" / company.company_code
                await db.delete(company)
                await db.commit()
                if company_directory.exists():
                    for item in company_directory.iterdir():
                        item.unlink()
                    company_directory.rmdir()
            user = await db.get(User, user_id)
            if user:
                await db.delete(user)
                await db.commit()
