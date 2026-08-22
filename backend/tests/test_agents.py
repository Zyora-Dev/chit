from datetime import date
import pytest,pytest_asyncio
from httpx import ASGITransport,AsyncClient
from sqlalchemy import delete,select
from app.core.security import create_access_token,hash_password
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.advance import AdvanceAllocation,AdvancePayment
from app.models.agent import AgentGroupAssignment,AgentLocation,AgentMemberAssignment,AgentShift,CollectionAgent
from app.models.chit import ChitGroup,ChitEnrollment,ChitPayment,LedgerEntry
from app.models.company import Company
from app.models.employee import Employee
from app.models.member import Member
from app.models.user import User
@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as value:yield value
@pytest.mark.asyncio
async def test_agent_assignment_shift_and_collection(client,monkeypatch):
    sent_emails=[]
    async def fake_email(*args,**kwargs):sent_emails.append(kwargs)
    monkeypatch.setattr("app.api.routes.agents.notify_payment_collection",fake_email)
    async with AsyncSessionLocal() as db:
        stale=await db.scalar(select(User).where(User.email=="agent-owner@example.com"))
        if stale:await db.delete(stale);await db.commit()
        stale_agent=await db.scalar(select(User).where(User.email=="field-agent@example.com"))
        if stale_agent:await db.delete(stale_agent);await db.commit()
        owner=User(email="agent-owner@example.com",password_hash=hash_password("StrongPassword123!"),role="owner",is_verified=True);db.add(owner);await db.flush();company=Company(company_code="ZCH-AGTTEST",owner_id=owner.id,name="Agent Test",mobile_number="+919999999994",email=owner.email);db.add(company);await db.flush();employee=Employee(company_id=company.id,employee_code="EMP-AGENT",full_name="Agent Employee",mobile_number="+919876540020",current_address="Nagercoil",department="Collection",designation="Agent",employment_type="permanent",work_mode="field",joining_date=date.today(),emergency_contact_name="Emergency",emergency_contact_relationship="Parent",emergency_contact_mobile="+919876540021",collection_agent_enabled=True);db.add(employee);member=Member(company_id=company.id,member_code="MEM-AGENT",full_name="Assigned Member",mobile_number="+919876540022",aadhaar_hash="d"*64,aadhaar_last4="1234",address_line_1="Street",city="Nagercoil",state="Tamil Nadu",postal_code="629001");db.add(member);await db.commit();owner_token=create_access_token(owner.id,owner.role);owner_id=owner.id;company_id=company.id;employee_id=employee.id;member_id=member.id
    oh={"Authorization":f"Bearer {owner_token}"}
    try:
        created=await client.post("/api/v1/admin/collection-agents",headers=oh,json={"employee_id":employee_id,"email":"field-agent@example.com","password":"StrongPassword123!"});assert created.status_code==201,created.text;agent_id=created.json()["id"]
        scheme=await client.post("/api/v1/chits",headers=oh,json={"scheme_name":"Agent Scheme","scheme_amount":12000,"start_date":str(date.today()),"duration_months":3});group=scheme.json();group_id=group["id"];await client.put(f"/api/v1/chits/{group_id}/members",headers=oh,json={"member_ids":[member_id]});detail=(await client.get(f"/api/v1/chits/{group_id}",headers=oh)).json();enrollment_id=detail["members"][0]["enrollment_id"];schedule_id=detail["schedules"][0]["id"];future_schedule_id=detail["schedules"][1]["id"]
        assigned=await client.put(f"/api/v1/admin/collection-agents/{agent_id}/assignments",headers=oh,json={"group_ids":[],"enrollment_ids":[enrollment_id]});assert assigned.status_code==200
        saved_assignments=(await client.get(f"/api/v1/admin/collection-agents/{agent_id}/assignments",headers=oh)).json();assert saved_assignments["enrollment_ids"]==[enrollment_id] and saved_assignments["members"][0]["member_name"]=="Assigned Member" and saved_assignments["members"][0]["scheme_name"]=="Agent Scheme"
        agent_register=(await client.get("/api/v1/admin/collection-agents",headers=oh)).json();assert agent_register[0]["assigned_members"][0]["member_name"]=="Assigned Member"
        login=await client.post("/api/v1/auth/login",json={"email":"field-agent@example.com","password":"StrongPassword123!"});assert login.status_code==200;agent_tokens=login.json();ah={"Authorization":f"Bearer {agent_tokens['access_token']}"}
        blocked=await client.get("/api/v1/members",headers=ah);assert blocked.status_code==403
        profile=await client.get("/api/v1/agent/profile",headers=ah);assert profile.status_code==200 and profile.json()["employee_code"]=="EMP-AGENT" and profile.json()["department"]=="Collection"
        checkin=await client.post("/api/v1/agent/check-in",headers=ah,json={"latitude":8.1833,"longitude":77.4119,"accuracy_meters":10});assert checkin.status_code==200
        blocked_deactivate=await client.put(f"/api/v1/admin/collection-agents/{agent_id}/status",headers=oh,json={"is_active":False});assert blocked_deactivate.status_code==409
        tasks=await client.get("/api/v1/agent/assignments",headers=ah);assert tasks.status_code==200 and len(tasks.json())==1
        collection=await client.post("/api/v1/agent/collections",headers=ah,json={"enrollment_id":enrollment_id,"schedule_id":schedule_id,"collection_type":"regular","amount_type":"partial","amount":2000,"payment_mode":"cash","latitude":8.1834,"longitude":77.4120});assert collection.status_code==201 and collection.json()["receipt_number"]
        installment_advance=await client.post("/api/v1/agent/collections",headers=ah,json={"enrollment_id":enrollment_id,"schedule_id":future_schedule_id,"collection_type":"advance","amount_type":"partial","amount":1000,"payment_mode":"upi","reference_number":"UPI-INST-ADV","latitude":8.1834,"longitude":77.4120});assert installment_advance.status_code==201
        refreshed=(await client.get("/api/v1/agent/assignments",headers=ah)).json();future_row=next(item for item in refreshed[0]["installments"] if item["schedule_id"]==future_schedule_id);assert future_row["status"]=="partial" and float(future_row["paid_amount"])==1000
        report=(await client.get("/api/v1/chits/collections/report",headers=oh)).json();assert any(item["receipt_number"]==installment_advance.json()["receipt_number"] and item["installment_number"]==2 for item in report["rows"])
        advances=(await client.get("/api/v1/advance-payments",headers=oh)).json();allocated=next(item for item in advances if item["reference_number"]=="UPI-INST-ADV");assert allocated["status"]=="allocated" and float(allocated["allocated_amount"])==1000 and float(allocated["available_amount"])==0
        advance=await client.post("/api/v1/agent/collections",headers=ah,json={"enrollment_id":enrollment_id,"schedule_id":None,"collection_type":"advance","amount_type":"partial","amount":1000,"payment_mode":"upi","reference_number":"UPI-AGT","latitude":8.1834,"longitude":77.4120});assert advance.status_code==201
        assert len(sent_emails)==3
        persistent=(await client.get("/api/v1/communications/notifications",headers=oh)).json();assert persistent["unread_count"]==3 and all(item["type"]=="payment" for item in persistent["items"])
        history=(await client.get("/api/v1/agent/collections",headers=ah)).json();assert history["today_count"]==3 and float(history["today_amount"])==4000 and len(history["rows"])==3;assert history["customers"][0]["name"]=="Assigned Member"
        filtered=(await client.get(f"/api/v1/agent/collections?date_from={date.today()}&date_to={date.today()}&customer=Assigned",headers=ah)).json();assert len(filtered["rows"])==3
        overall=(await client.get("/api/v1/dashboard/overall-report",headers=oh)).json();assert overall["transaction_count"]==3 and float(overall["total_inflow"])==4000 and float(overall["total_outflow"])==0
        overall_advances=(await client.get(f"/api/v1/dashboard/overall-report?transaction_type=advance&date_from={date.today()}&date_to={date.today()}",headers=oh)).json();assert overall_advances["transaction_count"]==2 and float(overall_advances["total_inflow"])==2000
        search=(await client.get("/api/v1/dashboard/search?q=Assigned",headers=oh)).json();assert any(item["type"]=="member" and item["title"]=="Assigned Member" for item in search)
        notifications=await client.get("/api/v1/dashboard/notifications",headers=oh);assert notifications.status_code==200 and "unread_count" in notifications.json() and isinstance(notifications.json()["items"],list)
        checkout=await client.post("/api/v1/agent/check-out",headers=ah,json={"latitude":8.1835,"longitude":77.4121});assert checkout.status_code==200
        deactivated=await client.put(f"/api/v1/admin/collection-agents/{agent_id}/status",headers=oh,json={"is_active":False});assert deactivated.status_code==200 and deactivated.json()["is_active"] is False
        blocked_login=await client.post("/api/v1/auth/login",json={"email":"field-agent@example.com","password":"StrongPassword123!"});assert blocked_login.status_code==401
        blocked_access=await client.get("/api/v1/agent/profile",headers=ah);assert blocked_access.status_code==401
        blocked_refresh=await client.post("/api/v1/auth/refresh",json={"refresh_token":agent_tokens["refresh_token"]});assert blocked_refresh.status_code==401
        reactivated=await client.put(f"/api/v1/admin/collection-agents/{agent_id}/status",headers=oh,json={"is_active":True});assert reactivated.status_code==200 and reactivated.json()["is_active"] is True
        after_checkout=await client.get("/api/v1/agent/collections",headers=ah);assert after_checkout.status_code==200
    finally:
        async with AsyncSessionLocal() as db:
            agent_ids=select(CollectionAgent.id).where(CollectionAgent.company_id==company_id);shift_ids=select(AgentShift.id).where(AgentShift.collection_agent_id.in_(agent_ids));await db.execute(delete(AgentLocation).where(AgentLocation.shift_id.in_(shift_ids)));await db.execute(delete(AgentShift).where(AgentShift.collection_agent_id.in_(agent_ids)));await db.execute(delete(AgentGroupAssignment).where(AgentGroupAssignment.collection_agent_id.in_(agent_ids)));await db.execute(delete(AgentMemberAssignment).where(AgentMemberAssignment.collection_agent_id.in_(agent_ids)));await db.execute(delete(LedgerEntry).where(LedgerEntry.company_id==company_id));await db.execute(delete(AdvanceAllocation).where(AdvanceAllocation.advance_payment_id.in_(select(AdvancePayment.id).where(AdvancePayment.company_id==company_id))));await db.execute(delete(AdvancePayment).where(AdvancePayment.company_id==company_id));await db.execute(delete(ChitPayment).where(ChitPayment.enrollment_id.in_(select(ChitEnrollment.id).join(ChitGroup).where(ChitGroup.company_id==company_id))));await db.execute(delete(ChitGroup).where(ChitGroup.company_id==company_id));await db.execute(delete(CollectionAgent).where(CollectionAgent.company_id==company_id));employee=await db.get(Employee,employee_id)
            if employee:await db.delete(employee)
            member=await db.get(Member,member_id)
            if member:await db.delete(member)
            company=await db.get(Company,company_id)
            if company:await db.delete(company)
            owner=await db.get(User,owner_id)
            if owner:await db.delete(owner)
            agent_user=await db.scalar(select(User).where(User.email=="field-agent@example.com"))
            if agent_user:await db.delete(agent_user)
            await db.commit()
