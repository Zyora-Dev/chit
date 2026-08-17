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
from app.models.member import Member, MemberReference
from app.models.user import User


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_member_creation_references_and_documents(client: AsyncClient):
    email = "member-module-owner@example.com"
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, password_hash=hash_password("StrongPassword123!"), role="owner", is_verified=True)
            db.add(user); await db.commit(); await db.refresh(user)
        company = await db.scalar(select(Company).where(Company.owner_id == user.id))
        if company is None:
            company = Company(company_code="ZCH-MEMBERTEST", owner_id=user.id, name="Member Test Chits", mobile_number="+919999999999", email=email)
            db.add(company); await db.commit(); await db.refresh(company)
        existing = await db.scalar(select(Member).where(Member.company_id == company.id, Member.mobile_number == "+919876543211"))
        if existing:
            await db.execute(delete(MemberReference).where(MemberReference.member_id == existing.id)); await db.delete(existing); await db.commit()
        token = create_access_token(user.id, user.role); user_id = user.id; company_id = company.id

    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "full_name": "Member Integration Test", "mobile_number": "+919876543211",
        "date_of_birth": "1992-04-18",
        "email": "member@example.com", "aadhaar_number": "123412341234", "pan": "ABCDE1234F",
        "nominee_name": "Member Nominee", "nominee_relationship": "Spouse",
        "nominee_mobile_number": "+919876500009", "nominee_date_of_birth": "1994-07-21",
        "bank_account_holder_name": "Member Integration Test", "bank_account_number": "123456789012",
        "bank_name": "State Bank of India", "bank_branch_name": "Nagercoil Main",
        "bank_ifsc_code": "SBIN0001234", "bank_account_type": "savings",
        "address_line_1": "12 Member Street", "city": "Nagercoil", "state": "Tamil Nadu",
        "postal_code": "629001", "country": "India",
        "references": [
            {"name": "Reference One", "mobile_number": "+919876500001", "relationship": "Friend"},
            {"name": "Reference Two", "mobile_number": "+919876500002", "relationship": "Relative"},
        ],
    }
    member_id = None
    try:
        response = await client.post("/api/v1/members", json=payload, headers=headers)
        assert response.status_code == 201, response.text
        member = response.json(); member_id = member["id"]
        assert member["aadhaar_last4"] == "1234" and "aadhaar_number" not in member
        assert member["date_of_birth"] == "1992-04-18"
        assert member["nominee_name"] == "Member Nominee"
        assert member["bank_ifsc_code"] == "SBIN0001234"
        assert member["bank_account_number"] == "123456789012"
        assert len(member["references"]) == 2

        response = await client.get("/api/v1/members?search=Integration", headers=headers)
        assert response.status_code == 200 and response.json()["total"] == 1

        pdf = b"%PDF-1.4\nmember document"
        png = b"\x89PNG\r\n\x1a\nmember photo"
        response = await client.post(
            f"/api/v1/members/{member_id}/documents", headers=headers,
            files={
                "photo": ("photo.png", png, "image/png"),
                "aadhaar_document": ("aadhaar.pdf", pdf, "application/pdf"),
                "pan_document": ("pan.pdf", pdf, "application/pdf"),
                "cheque": ("cheque.pdf", pdf, "application/pdf"),
                "bank_statement": ("statement.pdf", pdf, "application/pdf"),
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["photo_file_name"] == "photo.png"
        assert response.json()["aadhaar_document_file_name"] == "aadhaar.pdf"
        assert response.json()["pan_document_file_name"] == "pan.pdf"
        assert response.json()["cheque_file_name"] == "cheque.pdf"
        assert response.json()["bank_statement_file_name"] == "statement.pdf"

        response = await client.get(
            f"/api/v1/members/{member_id}/documents/aadhaar", headers=headers
        )
        assert response.status_code == 200
        assert response.content.startswith(b"%PDF-")

        response = await client.get(
            f"/api/v1/members/{member_id}/documents/unknown", headers=headers
        )
        assert response.status_code == 404

        update_payload = {
            **payload,
            "full_name": "Updated Member Name",
            "nominee_relationship": "Sibling",
            "bank_account_type": "current",
            "aadhaar_number": None,
            "references": [
                {"name": "Updated Reference", "mobile_number": "+919876500003", "relationship": "Colleague"}
            ],
        }
        response = await client.put(
            f"/api/v1/members/{member_id}", json=update_payload, headers=headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["full_name"] == "Updated Member Name"
        assert response.json()["aadhaar_last4"] == "1234"
        assert response.json()["nominee_relationship"] == "Sibling"
        assert response.json()["bank_account_type"] == "current"
        assert len(response.json()["references"]) == 1

        response = await client.delete(f"/api/v1/members/{member_id}", headers=headers)
        assert response.status_code == 204
        response = await client.get(f"/api/v1/members/{member_id}", headers=headers)
        assert response.status_code == 200 and response.json()["is_active"] is False
        restored = await client.post(f"/api/v1/members/{member_id}/restore",headers=headers)
        assert restored.status_code == 200 and restored.json()["is_active"] is True
        response = await client.delete(f"/api/v1/members/{member_id}", headers=headers)
        assert response.status_code == 204
    finally:
        async with AsyncSessionLocal() as db:
            if member_id:
                member = await db.get(Member, member_id)
                if member:
                    for path in (
                        member.photo_path, member.aadhaar_document_path, member.pan_document_path,
                        member.cheque_path, member.bank_statement_path,
                    ):
                        if path and Path(path).exists(): Path(path).unlink()
                    await db.execute(delete(MemberReference).where(MemberReference.member_id == member.id)); await db.delete(member); await db.commit()
            company = await db.get(Company, company_id)
            if company and company.company_code == "ZCH-MEMBERTEST": await db.delete(company); await db.commit()
            user = await db.get(User, user_id)
            if user and user.email == email: await db.delete(user); await db.commit()
