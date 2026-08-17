from datetime import date
import pytest,pytest_asyncio
from httpx import ASGITransport,AsyncClient
from sqlalchemy import delete,select
from app.core.security import create_access_token,hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.company import Company
from app.models.employee import Employee
from app.models.rbac import CompanyUser,Role
from app.models.user import User
@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as value:yield value
@pytest.mark.asyncio
async def test_employee_code_users_roles_and_fixed_agent_permissions(client):
    async with AsyncSessionLocal() as db:
        owner=User(email="rbac-owner@example.com",password_hash=hash_password("StrongPassword123!"),role="owner",is_verified=True);db.add(owner);await db.flush();company=Company(company_code="ZCH-RBACTEST",owner_id=owner.id,name="RBAC Test",mobile_number="+919999999993",email=owner.email);db.add(company);await db.flush();employee=Employee(company_id=company.id,employee_code="EMP-RBAC",full_name="RBAC Employee",mobile_number="+919876540030",current_address="Nagercoil",department="Admin",designation="Executive",employment_type="permanent",work_mode="office",joining_date=date.today(),emergency_contact_name="Emergency",emergency_contact_relationship="Parent",emergency_contact_mobile="+919876540031");db.add(employee);await db.commit();token=create_access_token(owner.id,owner.role);owner_id=owner.id;company_id=company.id;employee_id=employee.id
    h={"Authorization":f"Bearer {token}"}
    try:
        await client.get("/api/v1/admin/permissions",headers=h);roles=await client.get("/api/v1/admin/roles",headers=h);agent_role=next(item for item in roles.json() if item["name"]=="Collection Agent");assert agent_role["is_system"] and set(agent_role["permission_codes"])=={"agent.check_in","agent.location","agent.assignments","agent.collect","agent.receipt"}
        custom=await client.post("/api/v1/admin/roles",headers=h,json={"name":"Viewer","permission_codes":["dashboard.view","members.view"]});assert custom.status_code==201
        user=await client.post("/api/v1/admin/users",headers=h,json={"employee_id":employee_id,"role_id":custom.json()["id"],"password":"StrongPassword123!"});assert user.status_code==201 and user.json()["login_id"]=="EMP-RBAC";user_id=user.json()["id"]
        login=await client.post("/api/v1/auth/login",json={"email":"EMP-RBAC","password":"StrongPassword123!"});assert login.status_code==200
        disabled=await client.put(f"/api/v1/admin/users/{user_id}/status",headers=h,json={"is_active":False});assert disabled.status_code==200
        blocked=await client.post("/api/v1/auth/login",json={"email":"EMP-RBAC","password":"StrongPassword123!"});assert blocked.status_code==401
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(CompanyUser).where(CompanyUser.company_id==company_id));await db.execute(delete(Role).where(Role.company_id==company_id));employee=await db.get(Employee,employee_id)
            if employee:await db.delete(employee)
            company=await db.get(Company,company_id)
            if company:await db.delete(company)
            staff=await db.scalar(select(User).where(User.login_id=="EMP-RBAC"))
            if staff:await db.delete(staff)
            owner=await db.get(User,owner_id)
            if owner:await db.delete(owner)
            await db.commit()
