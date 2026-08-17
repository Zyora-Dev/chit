import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.security import create_access_token, hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.branch import Branch
from app.models.company import Company
from app.models.user import User


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value: yield value


@pytest.mark.asyncio
async def test_branch_crud_company_scope(client: AsyncClient):
    email = "branch-test-owner@example.com"
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(email=email, password_hash=hash_password("StrongPassword123!"), role="owner", is_verified=True); db.add(user); await db.commit(); await db.refresh(user)
        company = await db.scalar(select(Company).where(Company.owner_id == user.id))
        if not company:
            company = Company(company_code="ZCH-BRANCHTEST", owner_id=user.id, name="Branch Test", mobile_number="+919999999997", email=email); db.add(company); await db.commit(); await db.refresh(company)
        await db.execute(delete(Branch).where(Branch.company_id == company.id)); await db.commit()
        token = create_access_token(user.id, user.role); company_id = company.id; user_id = user.id
    headers = {"Authorization": f"Bearer {token}"}; branch_id = None
    payload = {"name":"Nagercoil Branch","mobile_number":"+919876500010","email":"branch@example.com","manager_name":"Branch Manager","address_line_1":"10 Branch Road","city":"Nagercoil","state":"Tamil Nadu","postal_code":"629001","country":"India"}
    try:
        created = await client.post("/api/v1/branches", headers=headers, json=payload)
        assert created.status_code == 201, created.text; branch_id = created.json()["id"]
        assert created.json()["branch_code"].startswith("BR-")
        listing = await client.get("/api/v1/branches", headers=headers)
        assert listing.status_code == 200 and len(listing.json()) == 1
        updated = await client.put(f"/api/v1/branches/{branch_id}", headers=headers, json={**payload, "name":"Updated Branch", "is_active":False})
        assert updated.status_code == 200 and updated.json()["name"] == "Updated Branch" and updated.json()["is_active"] is False
        removed = await client.delete(f"/api/v1/branches/{branch_id}", headers=headers)
        assert removed.status_code == 204; branch_id = None
        listing = await client.get("/api/v1/branches", headers=headers)
        assert listing.json() == []
    finally:
        async with AsyncSessionLocal() as db:
            if branch_id: await db.execute(delete(Branch).where(Branch.id == branch_id)); await db.commit()
            company = await db.get(Company, company_id)
            if company and company.company_code == "ZCH-BRANCHTEST": await db.delete(company); await db.commit()
            user = await db.get(User, user_id)
            if user and user.email == email: await db.delete(user); await db.commit()
