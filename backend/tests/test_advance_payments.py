from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.security import create_access_token, hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.advance import AdvanceAllocation, AdvancePayment
from app.models.audit import AuditLog
from app.models.chit import ChitGroup, LedgerEntry
from app.models.company import Company
from app.models.member import Member
from app.models.user import User


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        yield value


@pytest.mark.asyncio
async def test_advance_payment_allocation_and_audit(client: AsyncClient):
    email = "advance-test-owner@example.com"
    async with AsyncSessionLocal() as db:
        user = User(email=email, password_hash=hash_password("StrongPassword123!"), role="owner", is_verified=True)
        db.add(user); await db.flush()
        company = Company(company_code="ZCH-ADVTEST", owner_id=user.id, name="Advance Test", mobile_number="+919999999997", email=email)
        db.add(company); await db.flush()
        member = Member(company_id=company.id, member_code="MEM-ADVTEST", full_name="Advance Member", mobile_number="+919876543211", aadhaar_hash="c" * 64, aadhaar_last4="9012", address_line_1="Test", city="Nagercoil", state="Tamil Nadu", postal_code="629001")
        db.add(member); await db.commit()
        user_id, company_id, member_id = user.id, company.id, member.id
        token = create_access_token(user.id, user.role)
    headers = {"Authorization": f"Bearer {token}"}
    try:
        created = await client.post("/api/v1/chits", headers=headers, json={"scheme_name":"Advance Scheme","scheme_amount":12000,"start_date":"2026-09-15","duration_months":3})
        assert created.status_code == 201, created.text
        group = created.json(); group_id = group["id"]
        enrolled = await client.put(f"/api/v1/chits/{group_id}/members", headers=headers, json={"member_ids":[member_id]})
        assert enrolled.status_code == 200
        advance = await client.post("/api/v1/advance-payments", headers=headers, json={"group_id":group_id,"member_id":member_id,"amount":6000,"payment_date":str(date.today()),"payment_mode":"upi","reference_number":"ADV-UPI-1"})
        assert advance.status_code == 201, advance.text
        data = advance.json(); advance_id = data["id"]
        assert data["receipt_number"] and float(data["available_amount"]) == 6000
        allocated = await client.post(f"/api/v1/advance-payments/{advance_id}/allocate", headers=headers, json={"schedule_ids":None})
        assert allocated.status_code == 200, allocated.text
        assert float(allocated.json()["allocated_amount"]) == 6000
        assert allocated.json()["status"] == "allocated"
        details = await client.get(f"/api/v1/chits/{group_id}", headers=headers)
        payments = details.json()["payments"]
        assert len(payments) == 2 and all(row["payment_source"] == "advance" for row in payments)
        assert sum(float(row["amount"]) for row in payments) == 6000
        ledger = await client.get(f"/api/v1/chits/ledger/entries?scheme_id={group_id}", headers=headers)
        debits = sum(float(row["amount"]) for row in ledger.json() if row["entry_type"] == "debit")
        credits = sum(float(row["amount"]) for row in ledger.json() if row["entry_type"] == "credit")
        assert debits == credits == 12000
        audit = await client.get("/api/v1/audit-logs?entity_type=advance_payment", headers=headers)
        assert audit.status_code == 200
        assert {row["action"] for row in audit.json()} == {"create", "allocate"}
        assert all(row["actor_email"] == email for row in audit.json())
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(AdvanceAllocation).where(AdvanceAllocation.advance_payment_id.in_(select(AdvancePayment.id).where(AdvancePayment.company_id == company_id))))
            await db.execute(delete(AdvancePayment).where(AdvancePayment.company_id == company_id))
            await db.execute(delete(AuditLog).where(AuditLog.company_id == company_id))
            await db.execute(delete(LedgerEntry).where(LedgerEntry.company_id == company_id))
            await db.execute(delete(ChitGroup).where(ChitGroup.company_id == company_id))
            member = await db.get(Member, member_id)
            if member: await db.delete(member)
            company = await db.get(Company, company_id)
            if company: await db.delete(company)
            user = await db.get(User, user_id)
            if user: await db.delete(user)
            await db.commit()
