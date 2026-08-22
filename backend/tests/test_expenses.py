from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.security import create_access_token, hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.audit import AuditLog
from app.models.company import Company
from app.models.expense import Expense
from app.models.rbac import CompanyUser, Permission, Role
from app.models.user import User


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        yield value


@pytest.mark.asyncio
async def test_expense_filters_permissions_and_company_isolation(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        owner = User(email="expense-owner@example.com", password_hash=hash_password("StrongPassword123!"), role="owner", is_verified=True)
        other_owner = User(email="expense-other@example.com", password_hash=hash_password("StrongPassword123!"), role="owner", is_verified=True)
        staff = User(email="expense-staff@example.com", login_id="EXP-STAFF", password_hash=hash_password("StrongPassword123!"), role="staff", is_verified=True)
        db.add_all([owner, other_owner, staff]); await db.flush()
        company = Company(company_code="ZCH-EXPTEST", owner_id=owner.id, name="Expense Test", mobile_number="+919999999981", email=owner.email)
        other_company = Company(company_code="ZCH-EXPOTHER", owner_id=other_owner.id, name="Other Expense Test", mobile_number="+919999999982", email=other_owner.email)
        db.add_all([company, other_company]); await db.flush()
        owner_id, other_owner_id, staff_id = owner.id, other_owner.id, staff.id
        company_id, other_company_id = company.id, other_company.id
        owner_token = create_access_token(owner.id, owner.role)
        other_token = create_access_token(other_owner.id, other_owner.role)
        await db.commit()

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    other_headers = {"Authorization": f"Bearer {other_token}"}
    try:
        permissions_response = await client.get("/api/v1/admin/permissions", headers=owner_headers)
        assert permissions_response.status_code == 200
        assert {row["code"] for row in permissions_response.json()} >= {"expenses.view", "expenses.manage"}
        async with AsyncSessionLocal() as db:
            view_permission = await db.scalar(select(Permission).where(Permission.code == "expenses.view"))
            manage_permission = await db.scalar(select(Permission).where(Permission.code == "expenses.manage"))
            role = Role(company_id=company_id, name="Expense Viewer", created_by_user_id=owner_id, permissions=[view_permission])
            db.add(role); await db.flush()
            db.add(CompanyUser(company_id=company_id, user_id=staff_id, role_id=role.id))
            await db.commit(); role_id = role.id
        staff_headers = {"Authorization": f"Bearer {create_access_token(staff_id, 'staff')}"}

        food = await client.post("/api/v1/expenses", headers=owner_headers, json={
            "expense_date": str(date.today()), "category": "food", "amount": "450.50",
            "payee": "Town Cafe", "payment_mode": "upi", "reference_number": "UPI-FOOD-1",
            "description": "Team lunch", "notes": "Monthly meeting",
        })
        assert food.status_code == 201, food.text
        food_id = food.json()["id"]
        petrol = await client.post("/api/v1/expenses", headers=owner_headers, json={
            "expense_date": str(date.today()), "category": "petrol_allowance", "amount": "1000",
            "payee": "Field Executive", "payment_mode": "cash", "description": "Weekly petrol allowance",
        })
        assert petrol.status_code == 201, petrol.text
        other = await client.post("/api/v1/expenses", headers=other_headers, json={
            "expense_date": str(date.today()), "category": "recharge", "amount": "299",
            "payee": "Mobile Provider", "payment_mode": "card", "description": "Office mobile recharge",
        })
        assert other.status_code == 201, other.text

        filtered = await client.get("/api/v1/expenses?search=lunch&category=food", headers=owner_headers)
        assert filtered.status_code == 200
        assert filtered.json()["count"] == 1
        assert float(filtered.json()["total_amount"]) == 450.50
        assert filtered.json()["items"][0]["id"] == food_id
        assert filtered.json()["category_totals"] == {"food": "450.50"}

        view_only = await client.get("/api/v1/expenses", headers=staff_headers)
        assert view_only.status_code == 200 and view_only.json()["count"] == 2
        denied = await client.post("/api/v1/expenses", headers=staff_headers, json={
            "expense_date": str(date.today()), "category": "snacks", "amount": "150",
            "payment_mode": "cash", "description": "Office snacks",
        })
        assert denied.status_code == 403

        async with AsyncSessionLocal() as db:
            role = await db.get(Role, role_id)
            role.permissions = [view_permission := await db.scalar(select(Permission).where(Permission.code == "expenses.view")), manage_permission := await db.scalar(select(Permission).where(Permission.code == "expenses.manage"))]
            await db.commit()
        allowed = await client.post("/api/v1/expenses", headers=staff_headers, json={
            "expense_date": str(date.today()), "category": "snacks", "amount": "150",
            "payment_mode": "cash", "description": "Office snacks",
        })
        assert allowed.status_code == 201, allowed.text
        updated = await client.put(f"/api/v1/expenses/{food_id}", headers=owner_headers, json={
            "expense_date": str(date.today()), "category": "food", "amount": "500",
            "payee": "Town Cafe", "payment_mode": "upi", "reference_number": "UPI-FOOD-1",
            "description": "Updated team lunch", "notes": "Monthly meeting",
        })
        assert updated.status_code == 200 and float(updated.json()["amount"]) == 500
        removed = await client.delete(f"/api/v1/expenses/{food_id}", headers=owner_headers)
        assert removed.status_code == 204
        final_list = await client.get("/api/v1/expenses", headers=owner_headers)
        assert final_list.json()["count"] == 2
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(AuditLog).where(AuditLog.company_id.in_([company_id, other_company_id])))
            await db.execute(delete(Expense).where(Expense.company_id.in_([company_id, other_company_id])))
            await db.execute(delete(CompanyUser).where(CompanyUser.company_id == company_id))
            await db.execute(delete(Role).where(Role.company_id == company_id))
            for company_id_to_delete in (company_id, other_company_id):
                company_to_delete = await db.get(Company, company_id_to_delete)
                if company_to_delete: await db.delete(company_to_delete)
            for user_id in (staff_id, owner_id, other_owner_id):
                user = await db.get(User, user_id)
                if user: await db.delete(user)
            await db.commit()