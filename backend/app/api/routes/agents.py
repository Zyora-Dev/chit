from datetime import UTC,date,datetime
from decimal import Decimal
from fastapi import APIRouter,Depends,HTTPException,Query,Request
from sqlalchemy import func,select,update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.dependencies import get_current_user,require_owner
from app.api.routes.members import require_company
from app.core.security import hash_password
from app.db.session import get_db
from app.models.advance import AdvanceAllocation,AdvancePayment
from app.models.agent import AgentGroupAssignment,AgentLocation,AgentMemberAssignment,AgentShift,CollectionAgent
from app.models.chit import ChitAuction,ChitEnrollment,ChitGroup,ChitPayment,ChitSchedule
from app.models.company import Company
from app.models.employee import Employee
from app.models.member import Member
from app.models.session import AuthSession
from app.models.user import User
from app.schemas.agent import AgentAssignments,AgentCollectionCreate,AgentCreate,AgentStatusUpdate,LocationPoint
from app.services.accounting import document_number,post_entries
from app.services.audit import add_audit
from app.services.communications import add_notification,notify_payment_collection
router=APIRouter(prefix="/api/v1",tags=["Collection Agents"])
async def agent_context(db,user):
    if user.role!="collection_agent":raise HTTPException(status_code=403,detail="Collection agent access required")
    record=(await db.execute(select(CollectionAgent,Employee).join(Employee,CollectionAgent.employee_id==Employee.id).where(CollectionAgent.user_id==user.id,CollectionAgent.status=="active",Employee.is_active.is_(True),Employee.collection_agent_enabled.is_(True)))).one_or_none()
    if not record:raise HTTPException(status_code=403,detail="Collection agent account is inactive")
    return record
async def active_shift(db,agent_id):return await db.scalar(select(AgentShift).where(AgentShift.collection_agent_id==agent_id,AgentShift.status=="active"))
async def accessible_enrollment_ids(db,agent):
    direct=set((await db.execute(select(AgentMemberAssignment.enrollment_id).where(AgentMemberAssignment.collection_agent_id==agent.id,AgentMemberAssignment.is_active.is_(True)))).scalars().all());groups=set((await db.execute(select(AgentGroupAssignment.group_id).where(AgentGroupAssignment.collection_agent_id==agent.id,AgentGroupAssignment.is_active.is_(True)))).scalars().all())
    if groups:direct.update((await db.execute(select(ChitEnrollment.id).where(ChitEnrollment.group_id.in_(groups),ChitEnrollment.status=="active"))).scalars().all())
    return direct
@router.post("/admin/collection-agents",status_code=201)
async def create_agent(payload:AgentCreate,request:Request,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);employee=await db.scalar(select(Employee).where(Employee.id==payload.employee_id,Employee.company_id==company.id,Employee.is_active.is_(True),Employee.collection_agent_enabled.is_(True)))
    if not employee:raise HTTPException(status_code=400,detail="Select an active collection-enabled employee")
    if await db.scalar(select(CollectionAgent.id).where(CollectionAgent.employee_id==employee.id)):raise HTTPException(status_code=409,detail="Agent account already exists")
    account=User(email=str(payload.email).lower(),login_id=employee.employee_code,password_hash=hash_password(payload.password),role="collection_agent",is_verified=True,is_active=True);db.add(account);await db.flush();agent=CollectionAgent(company_id=company.id,employee_id=employee.id,user_id=account.id,created_by_user_id=user.id);db.add(agent);await db.flush();add_audit(db,company_id=company.id,user_id=user.id,action="create",entity_type="collection_agent",entity_id=agent.id,description=f"Created agent account for {employee.employee_code}",request=request,new_values={"employee_id":employee.id,"login_id":employee.employee_code});await db.commit();return {"id":agent.id,"employee_id":employee.id,"employee_name":employee.full_name,"login_id":employee.employee_code,"status":agent.status}
@router.get("/admin/collection-agents")
async def list_agents(user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);records=(await db.execute(select(CollectionAgent,Employee,User).join(Employee,CollectionAgent.employee_id==Employee.id).join(User,CollectionAgent.user_id==User.id).where(CollectionAgent.company_id==company.id).order_by(Employee.full_name))).all();result=[]
    for agent,employee,account in records:
        shift=await active_shift(db,agent.id);latest=await db.scalar(select(AgentLocation).where(AgentLocation.collection_agent_id==agent.id).order_by(AgentLocation.received_at.desc()))
        assigned_groups=(await db.execute(select(ChitGroup.id,ChitGroup.group_code,ChitGroup.scheme_name).join(AgentGroupAssignment,AgentGroupAssignment.group_id==ChitGroup.id).where(AgentGroupAssignment.collection_agent_id==agent.id,AgentGroupAssignment.is_active.is_(True)).order_by(ChitGroup.scheme_name))).all();assigned_members=(await db.execute(select(ChitEnrollment.id,Member.id,Member.member_code,Member.full_name,ChitGroup.scheme_name).join(AgentMemberAssignment,AgentMemberAssignment.enrollment_id==ChitEnrollment.id).join(Member,ChitEnrollment.member_id==Member.id).join(ChitGroup,ChitEnrollment.group_id==ChitGroup.id).where(AgentMemberAssignment.collection_agent_id==agent.id,AgentMemberAssignment.is_active.is_(True)).order_by(Member.full_name))).all()
        result.append({"id":agent.id,"employee_id":employee.id,"employee_code":employee.employee_code,"employee_name":employee.full_name,"email":account.email,"branch_id":employee.branch_id,"status":agent.status,"shift_status":shift.status if shift else "off_duty","shift_id":shift.id if shift else None,"last_latitude":latest.latitude if latest else None,"last_longitude":latest.longitude if latest else None,"last_location_at":latest.received_at if latest else None,"assigned_groups":[{"id":group_id,"group_code":code,"scheme_name":name} for group_id,code,name in assigned_groups],"assigned_members":[{"enrollment_id":enrollment_id,"member_id":member_id,"member_code":code,"member_name":name,"scheme_name":scheme_name} for enrollment_id,member_id,code,name,scheme_name in assigned_members]})
    return result
@router.put("/admin/collection-agents/{agent_id}/status")
async def update_agent_status(agent_id:int,payload:AgentStatusUpdate,request:Request,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);agent=await db.scalar(select(CollectionAgent).where(CollectionAgent.id==agent_id,CollectionAgent.company_id==company.id))
    if not agent:raise HTTPException(status_code=404,detail="Agent not found")
    if not payload.is_active and await active_shift(db,agent.id):raise HTTPException(status_code=409,detail="Check out the agent before deactivating the account")
    account=await db.get(User,agent.user_id);agent.status="active" if payload.is_active else "inactive";account.is_active=payload.is_active
    if not payload.is_active:await db.execute(update(AuthSession).where(AuthSession.user_id==account.id,AuthSession.revoked_at.is_(None)).values(revoked_at=datetime.now(UTC)))
    add_audit(db,company_id=company.id,user_id=user.id,action="activate" if payload.is_active else "deactivate",entity_type="collection_agent",entity_id=agent.id,description=f"{'Activated' if payload.is_active else 'Deactivated'} collection agent account",request=request,new_values={"is_active":payload.is_active});await db.commit();return {"status":agent.status,"is_active":account.is_active}
@router.put("/admin/collection-agents/{agent_id}/assignments")
async def assign(agent_id:int,payload:AgentAssignments,request:Request,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);agent=await db.scalar(select(CollectionAgent).where(CollectionAgent.id==agent_id,CollectionAgent.company_id==company.id))
    if not agent:raise HTTPException(status_code=404,detail="Agent not found")
    groups=set((await db.execute(select(ChitGroup.id).where(ChitGroup.company_id==company.id,ChitGroup.id.in_(payload.group_ids)))).scalars().all()) if payload.group_ids else set();enrollments=set((await db.execute(select(ChitEnrollment.id).join(ChitGroup).where(ChitGroup.company_id==company.id,ChitEnrollment.id.in_(payload.enrollment_ids)))).scalars().all()) if payload.enrollment_ids else set()
    if groups!=set(payload.group_ids) or enrollments!=set(payload.enrollment_ids):raise HTTPException(status_code=400,detail="Invalid scheme or member assignment")
    await db.execute(__import__('sqlalchemy').delete(AgentGroupAssignment).where(AgentGroupAssignment.collection_agent_id==agent.id));await db.execute(__import__('sqlalchemy').delete(AgentMemberAssignment).where(AgentMemberAssignment.collection_agent_id==agent.id));db.add_all([AgentGroupAssignment(company_id=company.id,collection_agent_id=agent.id,group_id=value,assigned_by_user_id=user.id) for value in groups]+[AgentMemberAssignment(company_id=company.id,collection_agent_id=agent.id,enrollment_id=value,assigned_by_user_id=user.id) for value in enrollments]);add_audit(db,company_id=company.id,user_id=user.id,action="assign",entity_type="collection_agent",entity_id=agent.id,description="Updated collection assignments",request=request,new_values={"group_ids":list(groups),"enrollment_ids":list(enrollments)});await db.commit();return {"group_ids":list(groups),"enrollment_ids":list(enrollments)}
@router.get("/admin/collection-agents/{agent_id}/assignments")
async def assignments(agent_id:int,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);agent=await db.scalar(select(CollectionAgent).where(CollectionAgent.id==agent_id,CollectionAgent.company_id==company.id));
    if not agent:raise HTTPException(status_code=404,detail="Agent not found")
    groups=(await db.execute(select(ChitGroup.id,ChitGroup.group_code,ChitGroup.scheme_name).join(AgentGroupAssignment,AgentGroupAssignment.group_id==ChitGroup.id).where(AgentGroupAssignment.collection_agent_id==agent.id,AgentGroupAssignment.is_active.is_(True)).order_by(ChitGroup.scheme_name))).all();members=(await db.execute(select(ChitEnrollment.id,Member.id,Member.member_code,Member.full_name,ChitGroup.scheme_name).join(AgentMemberAssignment,AgentMemberAssignment.enrollment_id==ChitEnrollment.id).join(Member,ChitEnrollment.member_id==Member.id).join(ChitGroup,ChitEnrollment.group_id==ChitGroup.id).where(AgentMemberAssignment.collection_agent_id==agent.id,AgentMemberAssignment.is_active.is_(True)).order_by(Member.full_name))).all()
    return {"group_ids":[item.id for item in groups],"enrollment_ids":[item.id for item in members],"groups":[{"id":item.id,"group_code":item.group_code,"scheme_name":item.scheme_name} for item in groups],"members":[{"enrollment_id":item.id,"member_id":item[1],"member_code":item.member_code,"member_name":item.full_name,"scheme_name":item.scheme_name} for item in members]}

@router.get("/admin/collection-agents/{agent_id}/locations")
async def agent_location_history(agent_id:int,shift_id:int|None=None,limit:int=500,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);agent=await db.scalar(select(CollectionAgent).where(CollectionAgent.id==agent_id,CollectionAgent.company_id==company.id))
    if not agent:raise HTTPException(status_code=404,detail="Agent not found")
    shift=await db.scalar(select(AgentShift).where(AgentShift.collection_agent_id==agent.id,*( [AgentShift.id==shift_id] if shift_id else [] )).order_by(AgentShift.checked_in_at.desc()))
    if not shift:return {"shift":None,"points":[]}
    bounded=max(1,min(limit,2000));points=list((await db.execute(select(AgentLocation).where(AgentLocation.collection_agent_id==agent.id,AgentLocation.shift_id==shift.id).order_by(AgentLocation.received_at.asc()).limit(bounded))).scalars().all())
    return {"shift":{"id":shift.id,"status":shift.status,"checked_in_at":shift.checked_in_at,"checked_out_at":shift.checked_out_at},"points":[{"latitude":point.latitude,"longitude":point.longitude,"accuracy_meters":point.accuracy_meters,"device_recorded_at":point.device_recorded_at,"received_at":point.received_at} for point in points]}
@router.post("/agent/check-in")
async def check_in(point:LocationPoint,request:Request,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    agent,employee=await agent_context(db,user)
    if await active_shift(db,agent.id):raise HTTPException(status_code=409,detail="Shift is already active")
    shift=AgentShift(company_id=agent.company_id,collection_agent_id=agent.id,branch_id=employee.branch_id,check_in_latitude=point.latitude,check_in_longitude=point.longitude,check_in_accuracy_meters=point.accuracy_meters);db.add(shift);await db.flush();db.add(AgentLocation(company_id=agent.company_id,collection_agent_id=agent.id,shift_id=shift.id,latitude=point.latitude,longitude=point.longitude,accuracy_meters=point.accuracy_meters,device_recorded_at=point.device_recorded_at));add_audit(db,company_id=agent.company_id,user_id=user.id,action="check_in",entity_type="agent_shift",entity_id=shift.id,description="Collection agent checked in",request=request,new_values={"latitude":str(point.latitude),"longitude":str(point.longitude)});await db.commit();return {"shift_id":shift.id,"status":"active","checked_in_at":shift.checked_in_at}
@router.get("/agent/status")
async def agent_status(user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    agent,employee=await agent_context(db,user);shift=await active_shift(db,agent.id);return {"agent_id":agent.id,"employee_code":employee.employee_code,"employee_name":employee.full_name,"shift_active":bool(shift),"shift_id":shift.id if shift else None,"checked_in_at":shift.checked_in_at if shift else None}
@router.get("/agent/profile")
async def agent_profile(user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    agent,employee=await agent_context(db,user)
    return {"agent_id":agent.id,"employee_id":employee.id,"employee_code":employee.employee_code,"full_name":employee.full_name,"date_of_birth":employee.date_of_birth,"gender":employee.gender,"blood_group":employee.blood_group,"mobile_number":employee.mobile_number,"personal_email":employee.personal_email,"official_email":employee.official_email,"current_address":employee.current_address,"department":employee.department,"designation":employee.designation,"employment_type":employee.employment_type,"work_mode":employee.work_mode,"joining_date":employee.joining_date,"status":employee.status,"kyc_status":employee.kyc_status,"emergency_contact_name":employee.emergency_contact_name,"emergency_contact_relationship":employee.emergency_contact_relationship,"emergency_contact_mobile":employee.emergency_contact_mobile}
@router.post("/agent/location")
async def location(point:LocationPoint,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    agent,_=await agent_context(db,user);shift=await active_shift(db,agent.id)
    if not shift:raise HTTPException(status_code=409,detail="Check in before sharing location")
    record=AgentLocation(company_id=agent.company_id,collection_agent_id=agent.id,shift_id=shift.id,latitude=point.latitude,longitude=point.longitude,accuracy_meters=point.accuracy_meters,device_recorded_at=point.device_recorded_at);db.add(record);await db.commit();return {"status":"recorded"}
@router.post("/agent/check-out")
async def check_out(point:LocationPoint,request:Request,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    agent,_=await agent_context(db,user);shift=await active_shift(db,agent.id)
    if not shift:raise HTTPException(status_code=409,detail="No active shift")
    db.add(AgentLocation(company_id=agent.company_id,collection_agent_id=agent.id,shift_id=shift.id,latitude=point.latitude,longitude=point.longitude,accuracy_meters=point.accuracy_meters,device_recorded_at=point.device_recorded_at));shift.status="completed";shift.checked_out_at=datetime.now(UTC);shift.check_out_latitude=point.latitude;shift.check_out_longitude=point.longitude;add_audit(db,company_id=agent.company_id,user_id=user.id,action="check_out",entity_type="agent_shift",entity_id=shift.id,description="Collection agent checked out",request=request);await db.commit();return {"status":"completed"}
@router.get("/agent/assignments")
async def agent_assignments(user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    agent,_=await agent_context(db,user)
    if not await active_shift(db,agent.id):raise HTTPException(status_code=409,detail="Check in to view assignments")
    ids=await accessible_enrollment_ids(db,agent);records=(await db.execute(select(ChitEnrollment,ChitGroup,Member).join(ChitGroup,ChitEnrollment.group_id==ChitGroup.id).join(Member,ChitEnrollment.member_id==Member.id).where(ChitEnrollment.id.in_(ids),ChitEnrollment.status=="active").options(selectinload(ChitGroup.schedules)))).all() if ids else [];result=[]
    for enrollment,group,member in records:
        schedules=[]
        today=date.today();current_month=(today.year,today.month)
        for schedule in sorted(group.schedules,key=lambda item:(item.installment_number,item.due_date,item.id)):
            if schedule.installment_number<enrollment.start_installment or enrollment.end_installment and schedule.installment_number>enrollment.end_installment:continue
            payment_paid=Decimal(await db.scalar(select(func.coalesce(func.sum(ChitPayment.amount),0)).where(ChitPayment.enrollment_id==enrollment.id,ChitPayment.schedule_id==schedule.id,ChitPayment.status!="reversed")))
            auction_paid=Decimal(await db.scalar(select(func.coalesce(func.sum(ChitAuction.settled_installment_amount),0)).where(ChitAuction.winner_enrollment_id==enrollment.id,ChitAuction.schedule_id==schedule.id,ChitAuction.status=="paid")))
            paid=payment_paid+auction_paid;balance=max(schedule.payable_amount-paid,Decimal("0"));schedule_month=(schedule.due_date.year,schedule.due_date.month)
            status="paid" if balance==0 else "partial" if paid>0 else "late_due" if schedule_month<current_month else "due" if schedule_month==current_month else "upcoming"
            schedules.append({"schedule_id":schedule.id,"installment_number":schedule.installment_number,"due_date":schedule.due_date,"payable_amount":schedule.payable_amount,"paid_amount":paid,"balance_amount":balance,"status":status,"collectable":status!="paid"})
        result.append({"enrollment_id":enrollment.id,"member_id":member.id,"member_code":member.member_code,"member_name":member.full_name,"mobile_number":member.mobile_number,"address":f"{member.address_line_1}, {member.city}","group_id":group.id,"group_code":group.group_code,"scheme_name":group.scheme_name,"installments":schedules})
    return result
@router.get("/agent/collections")
async def agent_collection_history(date_from:date|None=None,date_to:date|None=None,customer:str|None=Query(default=None,max_length=200),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    agent,_=await agent_context(db,user);customer_filter=customer.strip() if customer else None
    payment_query=select(ChitPayment,ChitEnrollment,ChitSchedule,ChitGroup,Member).join(ChitEnrollment,ChitPayment.enrollment_id==ChitEnrollment.id).join(ChitSchedule,ChitPayment.schedule_id==ChitSchedule.id).join(ChitGroup,ChitEnrollment.group_id==ChitGroup.id).join(Member,ChitEnrollment.member_id==Member.id).where(ChitGroup.company_id==agent.company_id,ChitPayment.collected_by_user_id==user.id,ChitPayment.status!="reversed",ChitPayment.payment_source!="advance")
    advance_query=select(AdvancePayment,ChitEnrollment,ChitGroup,Member).join(ChitEnrollment,AdvancePayment.enrollment_id==ChitEnrollment.id).join(ChitGroup,AdvancePayment.group_id==ChitGroup.id).join(Member,ChitEnrollment.member_id==Member.id).where(AdvancePayment.company_id==agent.company_id,AdvancePayment.received_by_user_id==user.id)
    if date_from:payment_query=payment_query.where(ChitPayment.payment_date>=date_from);advance_query=advance_query.where(AdvancePayment.payment_date>=date_from)
    if date_to:payment_query=payment_query.where(ChitPayment.payment_date<=date_to);advance_query=advance_query.where(AdvancePayment.payment_date<=date_to)
    if customer_filter:payment_query=payment_query.where(Member.full_name.ilike(f"%{customer_filter}%"));advance_query=advance_query.where(Member.full_name.ilike(f"%{customer_filter}%"))
    payments=(await db.execute(payment_query.order_by(ChitPayment.payment_date.desc(),ChitPayment.created_at.desc()))).all();advances=(await db.execute(advance_query.order_by(AdvancePayment.payment_date.desc(),AdvancePayment.created_at.desc()))).all();rows=[]
    for payment,enrollment,schedule,group,member in payments:
        payment_month=(payment.payment_date.year,payment.payment_date.month);due_month=(schedule.due_date.year,schedule.due_date.month);collection_type="late" if due_month<payment_month else "regular"
        rows.append({"id":f"payment-{payment.id}","payment_id":payment.id,"advance_id":None,"member_id":member.id,"member_name":member.full_name,"member_code":member.member_code,"scheme_name":group.scheme_name,"installment_number":schedule.installment_number,"collection_type":collection_type,"amount":payment.amount,"payment_date":payment.payment_date,"payment_mode":payment.payment_mode,"reference_number":payment.reference_number,"receipt_number":payment.receipt_number,"status":payment.status,"created_at":payment.created_at})
    for advance,enrollment,group,member in advances:
        allocation=await db.scalar(select(AdvanceAllocation).where(AdvanceAllocation.advance_payment_id==advance.id).order_by(AdvanceAllocation.created_at.desc()));schedule=await db.get(ChitSchedule,allocation.schedule_id) if allocation else None
        rows.append({"id":f"advance-{advance.id}","payment_id":allocation.payment_id if allocation else None,"advance_id":advance.id,"member_id":member.id,"member_name":member.full_name,"member_code":member.member_code,"scheme_name":group.scheme_name,"installment_number":schedule.installment_number if schedule else None,"collection_type":"advance","amount":advance.amount,"payment_date":advance.payment_date,"payment_mode":advance.payment_mode,"reference_number":advance.reference_number,"receipt_number":advance.receipt_number,"status":advance.status,"created_at":advance.created_at})
    rows.sort(key=lambda item:(item["payment_date"],item["created_at"]),reverse=True);today=date.today();today_rows=[item for item in rows if item["payment_date"]==today]
    customer_rows=(await db.execute(select(Member.id,Member.full_name,Member.member_code).join(ChitEnrollment,ChitEnrollment.member_id==Member.id).where(ChitEnrollment.id.in_(await accessible_enrollment_ids(db,agent))).distinct().order_by(Member.full_name))).all()
    return {"rows":rows,"total_amount":sum((item["amount"] for item in rows),Decimal("0")),"total_count":len(rows),"today_amount":sum((item["amount"] for item in today_rows),Decimal("0")),"today_count":len(today_rows),"customers":[{"id":member_id,"name":name,"member_code":code} for member_id,name,code in customer_rows]}
@router.post("/agent/collections",status_code=201)
async def collect(payload:AgentCollectionCreate,request:Request,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    agent,employee=await agent_context(db,user);shift=await active_shift(db,agent.id);installment_number=None
    if not shift:raise HTTPException(status_code=409,detail="Check in before collecting")
    if payload.enrollment_id not in await accessible_enrollment_ids(db,agent):raise HTTPException(status_code=403,detail="Member is not assigned to this agent")
    enrollment=await db.get(ChitEnrollment,payload.enrollment_id);group=await db.scalar(select(ChitGroup).where(ChitGroup.id==enrollment.group_id,ChitGroup.company_id==agent.company_id));member=await db.get(Member,enrollment.member_id)
    if payload.collection_type=="advance" and payload.schedule_id is None:
        receipt=document_number("ADV",group.group_code,date.today());advance=AdvancePayment(company_id=agent.company_id,group_id=group.id,enrollment_id=enrollment.id,branch_id=employee.branch_id,receipt_number=receipt,amount=payload.amount,allocated_amount=0,payment_date=date.today(),payment_mode=payload.payment_mode,reference_number=payload.reference_number,notes=payload.notes,status="available",received_by_user_id=user.id);db.add(advance);await db.flush();cash="cash_on_hand" if payload.payment_mode=="cash" else "bank_clearing";post_entries(db,company_id=agent.company_id,branch_id=employee.branch_id,group_id=group.id,member_id=member.id,source_type="advance_payment",source_id=advance.id,entry_date=date.today(),reference_number=receipt,posted_by_user_id=user.id,entries=[("debit",cash,payload.amount,"Agent advance collection"),("credit","member_advance_liability",payload.amount,"Member advance balance")]);entity_id=advance.id
    else:
        if payload.schedule_id is None:raise HTTPException(status_code=400,detail="Select an installment")
        schedule=await db.scalar(select(ChitSchedule).where(ChitSchedule.id==payload.schedule_id,ChitSchedule.group_id==group.id));
        if not schedule:raise HTTPException(status_code=400,detail="Invalid installment")
        installment_number=schedule.installment_number
        payment_paid=Decimal(await db.scalar(select(func.coalesce(func.sum(ChitPayment.amount),0)).where(ChitPayment.enrollment_id==enrollment.id,ChitPayment.schedule_id==schedule.id,ChitPayment.status!="reversed")))
        auction_paid=Decimal(await db.scalar(select(func.coalesce(func.sum(ChitAuction.settled_installment_amount),0)).where(ChitAuction.winner_enrollment_id==enrollment.id,ChitAuction.schedule_id==schedule.id,ChitAuction.status=="paid")))
        balance=schedule.payable_amount-payment_paid-auction_paid
        current_month=(date.today().year,date.today().month);schedule_month=(schedule.due_date.year,schedule.due_date.month)
        if balance<=0:raise HTTPException(status_code=409,detail="Installment is already paid")
        if schedule_month>current_month and payload.collection_type!="advance":raise HTTPException(status_code=409,detail="Use Advance for future installments")
        if payload.collection_type=="regular" and schedule_month!=current_month:raise HTTPException(status_code=400,detail="Use Late for previous unpaid installments")
        if payload.collection_type=="late" and schedule_month>=current_month:raise HTTPException(status_code=400,detail="Late collection applies only to previous installments")
        if payload.amount_type=="full" and payload.amount!=balance:raise HTTPException(status_code=400,detail=f"Full payment must equal balance of {balance}")
        if payload.amount_type=="partial" and payload.amount>=balance:raise HTTPException(status_code=400,detail="Use Full when paying the complete balance")
        if payload.amount>balance:raise HTTPException(status_code=400,detail=f"Amount exceeds balance of {balance}")
        cash="cash_on_hand" if payload.payment_mode=="cash" else "bank_clearing"
        if payload.collection_type=="advance":
            advance_receipt=document_number("ADV",group.group_code,date.today());advance=AdvancePayment(company_id=agent.company_id,group_id=group.id,enrollment_id=enrollment.id,branch_id=employee.branch_id,receipt_number=advance_receipt,amount=payload.amount,allocated_amount=payload.amount,payment_date=date.today(),payment_mode=payload.payment_mode,reference_number=payload.reference_number,notes=payload.notes,status="allocated",received_by_user_id=user.id);db.add(advance);await db.flush()
            receipt=document_number("RCP",group.group_code,date.today());payment=ChitPayment(enrollment_id=enrollment.id,schedule_id=schedule.id,amount=payload.amount,received_amount=payload.amount,payment_date=date.today(),payment_mode=payload.payment_mode,reference_number=advance_receipt,notes=f"Allocated from agent advance {advance_receipt}" if not payload.notes else f"{payload.notes} · Allocated from agent advance {advance_receipt}",receipt_number=receipt,branch_id=employee.branch_id,collected_by_user_id=user.id,payment_source="advance",status="posted",collection_location_text=payload.location_text,collection_latitude=payload.latitude,collection_longitude=payload.longitude);db.add(payment);await db.flush();db.add(AdvanceAllocation(advance_payment_id=advance.id,payment_id=payment.id,schedule_id=schedule.id,amount=payload.amount,allocated_by_user_id=user.id))
            post_entries(db,company_id=agent.company_id,branch_id=employee.branch_id,group_id=group.id,member_id=member.id,source_type="advance_payment",source_id=advance.id,entry_date=date.today(),reference_number=advance_receipt,posted_by_user_id=user.id,entries=[("debit",cash,payload.amount,"Agent advance collection"),("credit","member_advance_liability",payload.amount,"Member advance balance")]);post_entries(db,company_id=agent.company_id,branch_id=employee.branch_id,group_id=group.id,member_id=member.id,source_type="advance_allocation",source_id=payment.id,entry_date=date.today(),reference_number=receipt,posted_by_user_id=user.id,entries=[("debit","member_advance_liability",payload.amount,f"Advance allocated to installment #{schedule.installment_number}"),("credit","member_installment_receivable",payload.amount,f"Installment #{schedule.installment_number} paid from advance")]);entity_id=advance.id
        else:
            receipt=document_number("RCP",group.group_code,date.today());payment=ChitPayment(enrollment_id=enrollment.id,schedule_id=schedule.id,amount=payload.amount,received_amount=payload.amount,payment_date=date.today(),payment_mode=payload.payment_mode,reference_number=payload.reference_number,notes=payload.notes,receipt_number=receipt,branch_id=employee.branch_id,collected_by_user_id=user.id,payment_source="agent",status="posted",collection_location_text=payload.location_text,collection_latitude=payload.latitude,collection_longitude=payload.longitude);db.add(payment);await db.flush();post_entries(db,company_id=agent.company_id,branch_id=employee.branch_id,group_id=group.id,member_id=member.id,source_type="payment",source_id=payment.id,entry_date=date.today(),reference_number=receipt,posted_by_user_id=user.id,entries=[("debit",cash,payload.amount,"Agent collection"),("credit","member_installment_receivable",payload.amount,f"Installment #{schedule.installment_number}")]);entity_id=payment.id
    company=await db.get(Company,agent.company_id);notification_entity_id=payment.id if payload.collection_type!="advance" else entity_id;notification_href=f"/dashboard/receipts/{payment.id}" if payload.collection_type!="advance" else "/dashboard/advance-payments";add_notification(db,company_id=agent.company_id,user_id=company.owner_id,title=f"Payment collected · {member.full_name}",message=f"₹{payload.amount} received for {group.scheme_name} via {payload.payment_mode.upper()} · {receipt} · agent {employee.full_name}",notification_type="payment",href=notification_href,entity_type="payment" if payload.collection_type!="advance" else "advance_payment",entity_id=notification_entity_id);db.add(AgentLocation(company_id=agent.company_id,collection_agent_id=agent.id,shift_id=shift.id,latitude=payload.latitude,longitude=payload.longitude));add_audit(db,company_id=agent.company_id,user_id=user.id,action="collect",entity_type="agent_collection",entity_id=entity_id,description=f"Agent recorded {payload.collection_type} collection",request=request,new_values={"amount":str(payload.amount),"amount_type":payload.amount_type,"receipt":receipt,"member_id":member.id});await db.commit();await notify_payment_collection(db,company=company,member_name=member.full_name,scheme_name=group.scheme_name,amount=payload.amount,receipt_number=receipt,payment_mode=payload.payment_mode,source=f"agent_{payload.collection_type}",entity_id=notification_entity_id,add_in_app=False,member_mobile=member.mobile_number,installment_number=installment_number,collector_name=employee.full_name);return {"id":entity_id,"receipt_number":receipt,"amount":payload.amount,"collection_type":payload.collection_type,"amount_type":payload.amount_type}
