from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport,AsyncClient
from sqlalchemy import delete,select

from app.core.security import create_access_token,hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.company import Company
from app.models.employee import Employee
from app.models.user import User

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as value:yield value

@pytest.mark.asyncio
async def test_employee_master_salary_documents_kyc_archive(client):
    email="employee-test-owner@example.com"
    async with AsyncSessionLocal() as db:
        user=User(email=email,password_hash=hash_password("StrongPassword123!"),role="owner",is_verified=True);db.add(user);await db.flush();company=Company(company_code="ZCH-EMPTEST",owner_id=user.id,name="Employee Test",mobile_number="+919999999996",email=email);db.add(company);await db.commit();token=create_access_token(user.id,user.role);user_id=user.id;company_id=company.id
    headers={"Authorization":f"Bearer {token}"};employee_id=None
    payload={"full_name":"Employee One","date_of_birth":"1990-01-01","gender":"male","mobile_number":"+919876540001","personal_email":"employee@example.com","current_address":"12 Employee Street, Nagercoil","department":"Collection","designation":"Agent","employment_type":"permanent","work_mode":"field","joining_date":str(date.today()),"collection_agent_enabled":True,"status":"active","emergency_contact_name":"Emergency One","emergency_contact_relationship":"Spouse","emergency_contact_mobile":"+919876540002","nominee_name":"Nominee One","nominee_relationship":"Spouse","nominee_share_percent":100,"bank_account_holder_name":"Employee One","bank_account_number":"123456789012","bank_name":"State Bank","bank_branch_name":"Nagercoil","bank_ifsc_code":"SBIN0001234","bank_account_type":"savings","aadhaar_number":"123412341234","pan":"ABCDE1234F","uan":"123456789012","pf_member_id":"PF-001","esic_ip_number":"1234567890","professional_tax_applicable":True,"labour_welfare_fund_applicable":True,"tax_regime":"new"}
    try:
        response=await client.post("/api/v1/employees",headers=headers,json=payload);assert response.status_code==201,response.text;employee=response.json();employee_id=employee["id"];assert employee["aadhaar_last4"]=="1234" and "aadhaar_number" not in employee
        listing=await client.get("/api/v1/employees?search=Employee",headers=headers);assert listing.status_code==200 and listing.json()["total"]==1
        salary=await client.post(f"/api/v1/employees/{employee_id}/salary",headers=headers,json={"effective_from":str(date.today()),"annual_ctc":600000,"basic":25000,"hra":10000,"allowances":5000,"incentives":1000,"employee_pf":1800,"employee_esi":300,"professional_tax":200,"tds":1000,"other_deductions":0});assert salary.status_code==200 and float(salary.json()["net_salary"])==37700
        pdf=b"%PDF-1.4\nemployee document"
        for document_type in ("aadhaar","pan","bank_proof"):
            uploaded=await client.post(f"/api/v1/employees/{employee_id}/documents",headers=headers,data={"document_type":document_type},files={"file":(f"{document_type}.pdf",pdf,"application/pdf")});assert uploaded.status_code==201,uploaded.text
        reviewed=await client.put(f"/api/v1/employees/{employee_id}/kyc",headers=headers,json={"aadhaar_status":"verified","pan_status":"verified","bank_status":"verified","notes":"Documents matched"});assert reviewed.status_code==200 and reviewed.json()["kyc_status"]=="verified"
        archived=await client.delete(f"/api/v1/employees/{employee_id}?reason=Employment%20ended",headers=headers);assert archived.status_code==204
        hidden=await client.get("/api/v1/employees",headers=headers);assert hidden.json()["total"]==0
        restored=await client.post(f"/api/v1/employees/{employee_id}/restore",headers=headers);assert restored.status_code==200 and restored.json()["is_active"] is True
    finally:
        async with AsyncSessionLocal() as db:
            employee=await db.get(Employee,employee_id) if employee_id else None
            if employee:
                for doc in employee.documents:
                    from pathlib import Path
                    Path(doc.file_path).unlink(missing_ok=True)
                await db.delete(employee)
            company=await db.get(Company,company_id)
            if company:await db.delete(company)
            user=await db.get(User,user_id)
            if user:await db.delete(user)
            await db.commit()
