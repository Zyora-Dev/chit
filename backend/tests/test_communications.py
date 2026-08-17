from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import pytest,pytest_asyncio
from httpx import ASGITransport,AsyncClient
from sqlalchemy import delete,select
from app.core.security import create_access_token,hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.communication import CommunicationSettings,InAppNotification
from app.models.user import User
from app.models.company import Company
from app.services.communications import notify_payment_collection

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as value:yield value

@pytest.mark.asyncio
async def test_communication_settings_and_notifications(client):
    email="communications-owner@example.com";user_id=company_id=None
    async with AsyncSessionLocal() as db:
        existing=await db.scalar(select(User).where(User.email==email))
        if existing:await db.delete(existing);await db.commit()
        owner=User(email=email,password_hash=hash_password("StrongPassword123!"),role="owner",is_verified=True);db.add(owner);await db.flush();company=Company(company_code="ZCH-COMMTEST",owner_id=owner.id,name="Communication Test",mobile_number="+919999999981",email=email);db.add(company);await db.commit();user_id=owner.id;company_id=company.id
    headers={"Authorization":f"Bearer {create_access_token(user_id,'owner')}"}
    try:
        initial=await client.get("/api/v1/communications/settings",headers=headers);assert initial.status_code==200 and initial.json()["access_token_configured"] is False
        invalid=await client.put("/api/v1/communications/settings",headers=headers,json={"admin_email":email,"email_payment_notifications":True,"whatsapp_enabled":True,"whatsapp_phone_number_id":"12345","whatsapp_business_account_id":"67890","whatsapp_access_token":None,"whatsapp_api_version":"v23.0"});assert invalid.status_code==400
        saved=await client.put("/api/v1/communications/settings",headers=headers,json={"admin_email":email,"email_payment_notifications":True,"whatsapp_enabled":True,"whatsapp_phone_number_id":"12345","whatsapp_business_account_id":"67890","whatsapp_access_token":"secret-meta-token","whatsapp_api_version":"v23.0"});assert saved.status_code==200 and saved.json()["access_token_configured"] is True and "whatsapp_access_token" not in saved.json()
        async with AsyncSessionLocal() as db:
            config=await db.scalar(select(CommunicationSettings).where(CommunicationSettings.company_id==company_id));assert config.whatsapp_access_token_encrypted and "secret-meta-token" not in config.whatsapp_access_token_encrypted
            db.add(InAppNotification(company_id=company_id,user_id=user_id,notification_type="payment",title="Payment collected",message="₹1000 received",href="/dashboard/collections",entity_type="payment",entity_id=1));await db.commit()
        feed=await client.get("/api/v1/communications/notifications",headers=headers);assert feed.status_code==200 and feed.json()["unread_count"]==1;notification_id=feed.json()["items"][0]["id"]
        marked=await client.post("/api/v1/communications/notifications/read",headers=headers,json={"notification_ids":[notification_id]});assert marked.status_code==200
        feed=await client.get("/api/v1/communications/notifications",headers=headers);assert feed.json()["unread_count"]==0 and feed.json()["items"][0]["read_at"]
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(InAppNotification).where(InAppNotification.company_id==company_id));await db.execute(delete(CommunicationSettings).where(CommunicationSettings.company_id==company_id));company=await db.get(Company,company_id)
            if company:await db.delete(company)
            owner=await db.get(User,user_id)
            if owner:await db.delete(owner)
            await db.commit()


@pytest.mark.asyncio
async def test_installment_collection_sends_member_and_owner_templates(monkeypatch):
    sends=[]
    config=SimpleNamespace(whatsapp_enabled=True,email_payment_notifications=False,admin_email=None)
    company=SimpleNamespace(id=91,owner_id=7,mobile_number="+919100000001")

    async def fake_settings(db,company):return config
    async def fake_send(config,**kwargs):sends.append(kwargs);return {"messages":[{"id":f"wamid.{len(sends)}"}]}

    monkeypatch.setattr("app.services.communications.get_communication_settings",fake_settings)
    monkeypatch.setattr("app.services.communications.send_whatsapp_template",fake_send)
    await notify_payment_collection(SimpleNamespace(),company=company,member_name="Assigned Member",scheme_name="Agent Scheme",amount=Decimal("2000"),receipt_number="RCP-1001",payment_mode="cash",source="agent_regular",entity_id=10,add_in_app=False,member_mobile="+919100000002",installment_number=3,collector_name="Agent Employee")

    assert sends==[
        {"recipient":"+919100000002","template_name":"collection_success_member","language_code":"en","body_parameters":["Assigned Member","3","2,000.00","Agent Scheme","RCP-1001"]},
        {"recipient":"+919100000001","template_name":"collection_success_admin","language_code":"en","body_parameters":["Assigned Member","3","2,000.00","Agent Scheme","Agent Employee","RCP-1001"]},
    ]
