from datetime import date
import pytest,pytest_asyncio
from httpx import ASGITransport,AsyncClient
from sqlalchemy import delete,select
from app.core.security import create_access_token,hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.company import Company
from app.models.employee import Employee,EmployeeSalaryStructure
from app.models.payroll import PayrollRun
from app.models.user import User
@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as value:yield value
@pytest.mark.asyncio
async def test_monthly_payroll_lifecycle(client):
    async with AsyncSessionLocal() as db:
        user=User(email="payroll-owner@example.com",password_hash=hash_password("StrongPassword123!"),role="owner",is_verified=True);db.add(user);await db.flush();company=Company(company_code="ZCH-PAYTEST",owner_id=user.id,name="Payroll Test",mobile_number="+919999999995",email=user.email);db.add(company);await db.flush();employee=Employee(company_id=company.id,employee_code="EMP-PAYTEST",full_name="Payroll Employee",mobile_number="+919876540010",current_address="Nagercoil",department="Admin",designation="Executive",employment_type="permanent",work_mode="office",joining_date=date(2026,1,1),emergency_contact_name="Emergency",emergency_contact_relationship="Parent",emergency_contact_mobile="+919876540011");db.add(employee);await db.flush();salary=EmployeeSalaryStructure(employee_id=employee.id,effective_from=date(2026,1,1),annual_ctc=480000,basic=25000,hra=10000,allowances=5000,incentives=0,employee_pf=1800,employee_esi=300,professional_tax=200,tds=1000,other_deductions=0,gross_salary=40000,net_salary=36700,created_by_user_id=user.id);db.add(salary);await db.commit();token=create_access_token(user.id,user.role);company_id=company.id;user_id=user.id;employee_id=employee.id
    headers={"Authorization":f"Bearer {token}"}
    try:
        created=await client.post("/api/v1/payroll/runs",headers=headers,json={"payroll_year":2026,"payroll_month":8});assert created.status_code==201,created.text;run=created.json();assert run["employee_count"]==1 and float(run["total_net_salary"])==36700;run_id=run["id"];item=run["items"][0]
        adjusted=await client.put(f"/api/v1/payroll/runs/{run_id}/items/{item['id']}/days",headers=headers,json={"payable_days":30,"lop_days":1});assert adjusted.status_code==200 and float(adjusted.json()["total_net_salary"])<36700
        approved=await client.post(f"/api/v1/payroll/runs/{run_id}/approve",headers=headers,json={"approval_notes":"Verified"});assert approved.status_code==200 and approved.json()["status"]=="approved"
        proof=b"%PDF-1.4\npayroll proof";paid=await client.post(f"/api/v1/payroll/runs/{run_id}/pay",headers=headers,data={"payment_date":"2026-08-31","payment_mode":"bank","payment_reference_number":"PAY-BANK-1"},files={"payment_proof":("proof.pdf",proof,"application/pdf")});assert paid.status_code==200 and paid.json()["status"]=="paid" and paid.json()["voucher_number"]
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(PayrollRun).where(PayrollRun.company_id==company_id));employee=await db.get(Employee,employee_id)
            if employee:await db.delete(employee)
            company=await db.get(Company,company_id)
            if company:await db.delete(company)
            user=await db.get(User,user_id)
            if user:await db.delete(user)
            await db.commit()
