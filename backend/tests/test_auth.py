import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.api.routes import auth as auth_routes
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.otp import EmailOTP
from app.models.user import User


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_complete_authentication_flow(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    email = "auth-flow-test@example.com"
    original_password = "StrongPassword123!"
    new_password = "NewStrongPassword456!"
    sent_messages: list[tuple[str, str, str]] = []

    async def fake_send_otp_email(recipient: str, otp: str, purpose: str) -> None:
        sent_messages.append((recipient, otp, purpose))

    monkeypatch.setattr(auth_routes, "send_otp_email", fake_send_otp_email)
    monkeypatch.setattr(auth_routes, "generate_otp", lambda: "123456")

    async with AsyncSessionLocal() as db:
        existing = await db.scalar(select(User).where(User.email == email))
        if existing:
            await db.execute(delete(EmailOTP).where(EmailOTP.user_id == existing.id))
            await db.delete(existing)
            await db.commit()

    try:
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": original_password},
        )
        assert response.status_code == 201
        assert sent_messages[-1] == (email, "123456", "email_verification")

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": original_password},
        )
        assert response.status_code == 403

        response = await client.post(
            "/api/v1/auth/verify-email",
            json={"email": email, "otp": "123456"},
        )
        assert response.status_code == 200

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": original_password},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert claims["role"] == "owner"

        response = await client.post(
            "/api/v1/auth/forgot-password", json={"email": email}
        )
        assert response.status_code == 200
        assert sent_messages[-1] == (email, "123456", "password_reset")

        response = await client.post(
            "/api/v1/auth/reset-password",
            json={"email": email, "otp": "123456", "new_password": new_password},
        )
        assert response.status_code == 200

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": new_password},
        )
        assert response.status_code == 200
    finally:
        async with AsyncSessionLocal() as db:
            user = await db.scalar(select(User).where(User.email == email))
            if user:
                await db.execute(delete(EmailOTP).where(EmailOTP.user_id == user.id))
                await db.delete(user)
                await db.commit()
