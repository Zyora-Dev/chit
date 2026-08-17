import pyotp
import pytest
import pytest_asyncio
from httpx import ASGITransport,AsyncClient
from sqlalchemy import delete,select
from app.core.security import create_access_token,hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.session import AuthSession,MfaChallenge
from app.models.user import User

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as value:yield value

@pytest.mark.asyncio
async def test_security_settings_mfa_and_sessions(client):
    email="security-settings@example.com";password="StrongPassword123!";user_id=None
    async with AsyncSessionLocal() as db:
        existing=await db.scalar(select(User).where(User.email==email))
        if existing:await db.delete(existing);await db.commit()
        user=User(email=email,password_hash=hash_password(password),role="owner",is_verified=True);db.add(user);await db.commit();await db.refresh(user);user_id=user.id
    headers={"Authorization":f"Bearer {create_access_token(user_id,'owner')}"}
    try:
        status=await client.get("/api/v1/auth/security",headers=headers);assert status.status_code==200 and status.json()["mfa_enabled"] is False
        bad=await client.post("/api/v1/auth/change-password",headers=headers,json={"current_password":"WrongPassword123!","new_password":"DifferentPassword456!"});assert bad.status_code==400
        setup=await client.post("/api/v1/auth/mfa/setup",headers=headers,json={"current_password":password});assert setup.status_code==200;secret=setup.json()["secret"];assert setup.json()["qr_code_data_url"].startswith("data:image/png;base64,")
        confirm=await client.post("/api/v1/auth/mfa/confirm",headers=headers,json={"code":pyotp.TOTP(secret).now()});assert confirm.status_code==200 and len(confirm.json()["recovery_codes"])==10;recovery=confirm.json()["recovery_codes"][0]
        login=await client.post("/api/v1/auth/login",json={"email":email,"password":password});assert login.status_code==200 and login.json()["mfa_required"] is True and login.json()["access_token"] is None
        verified=await client.post("/api/v1/auth/mfa/verify-login",json={"challenge_token":login.json()["challenge_token"],"code":pyotp.TOTP(secret).now()});assert verified.status_code==200 and verified.json()["access_token"] and verified.json()["refresh_token"]
        sessions=await client.get("/api/v1/auth/sessions",headers=headers);assert sessions.status_code==200 and len(sessions.json())>=1
        second=await client.post("/api/v1/auth/login",json={"email":email,"password":password});used=await client.post("/api/v1/auth/mfa/verify-login",json={"challenge_token":second.json()["challenge_token"],"code":recovery});assert used.status_code==200
        third=await client.post("/api/v1/auth/login",json={"email":email,"password":password});reused=await client.post("/api/v1/auth/mfa/verify-login",json={"challenge_token":third.json()["challenge_token"],"code":recovery});assert reused.status_code==401
        revoke=await client.post("/api/v1/auth/sessions/revoke-all",headers=headers);assert revoke.status_code==200
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(MfaChallenge).where(MfaChallenge.user_id==user_id));await db.execute(delete(AuthSession).where(AuthSession.user_id==user_id));user=await db.get(User,user_id)
            if user:await db.delete(user)
            await db.commit()
