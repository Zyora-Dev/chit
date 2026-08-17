from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import require_owner
from app.api.routes.members import require_company
from app.db.session import get_db
from app.models.advance import AdvancePayment
from app.models.chit import ChitAuction, ChitEnrollment, ChitGroup, ChitPayment, ChitSchedule, PaymentRefund
from app.models.member import Member
from app.models.employee import Employee
from app.models.audit import AuditLog
from app.models.payroll import PayrollRun
from app.models.user import User

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@router.get("/search")
async def global_search(q:str=Query(min_length=2,max_length=100),user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);term=f"%{q.strip()}%";members=(await db.execute(select(Member).where(Member.company_id==company.id,Member.full_name.ilike(term)).limit(6))).scalars().all();groups=(await db.execute(select(ChitGroup).where(ChitGroup.company_id==company.id,ChitGroup.scheme_name.ilike(term)).limit(6))).scalars().all();employees=(await db.execute(select(Employee).where(Employee.company_id==company.id,Employee.full_name.ilike(term)).limit(6))).scalars().all();payments=(await db.execute(select(ChitPayment,Member).join(ChitEnrollment,ChitPayment.enrollment_id==ChitEnrollment.id).join(ChitGroup,ChitEnrollment.group_id==ChitGroup.id).join(Member,ChitEnrollment.member_id==Member.id).where(ChitGroup.company_id==company.id,ChitPayment.receipt_number.ilike(term)).limit(6))).all();return [{"type":"member","id":item.id,"title":item.full_name,"subtitle":f"{item.member_code} · {item.mobile_number}","href":f"/dashboard/members/{item.id}"} for item in members]+[{"type":"scheme","id":item.id,"title":item.scheme_name,"subtitle":item.group_code,"href":f"/dashboard/chits/{item.id}"} for item in groups]+[{"type":"employee","id":item.id,"title":item.full_name,"subtitle":f"{item.employee_code} · {item.designation}","href":f"/dashboard/employees/{item.id}"} for item in employees]+[{"type":"receipt","id":payment.id,"title":payment.receipt_number,"subtitle":f"{member.full_name} · {payment.amount}","href":f"/dashboard/receipts/{payment.id}"} for payment,member in payments]


@router.get("/notifications")
async def notifications(user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);items=[];pending_kyc=list((await db.execute(select(Member).where(Member.company_id==company.id,Member.is_active.is_(True),Member.kyc_status=="pending").order_by(Member.created_at.desc()).limit(5))).scalars().all());pending_auctions=(await db.execute(select(ChitAuction,ChitGroup).join(ChitGroup,ChitAuction.group_id==ChitGroup.id).where(ChitGroup.company_id==company.id,ChitAuction.status.in_(["pending","approved"])).options(selectinload(ChitGroup.schedules)).order_by(ChitAuction.created_at.desc()).limit(5))).all();recent_audit=(await db.execute(select(AuditLog).where(AuditLog.company_id==company.id).order_by(AuditLog.created_at.desc()).limit(5))).scalars().all();items.extend({"id":f"kyc-{m.id}","type":"kyc","title":f"KYC pending · {m.full_name}","message":m.member_code,"created_at":m.created_at,"href":f"/dashboard/members/{m.id}"} for m in pending_kyc);items.extend({"id":f"auction-{a.id}","type":"auction","title":f"Auction {a.status} · {g.scheme_name}","message":f"Installment #{next((s.installment_number for s in g.schedules if s.id==a.schedule_id),'—')}","created_at":a.created_at,"href":"/dashboard/auctions"} for a,g in pending_auctions);items.extend({"id":f"audit-{a.id}","type":"activity","title":a.description,"message":f"{a.action} · {a.entity_type}","created_at":a.created_at,"href":"/dashboard/audit-history"} for a in recent_audit);return {"unread_count":len(pending_kyc)+len(pending_auctions),"items":sorted(items,key=lambda item:item["created_at"],reverse=True)[:12]}


@router.get("/overall-report")
async def overall_report(
    date_from:date|None=None,date_to:date|None=None,
    transaction_type:str|None=Query(default=None,pattern=r"^(collection|advance|refund|auction_payout|payroll)$"),
    scheme_id:int|None=None,member_id:int|None=None,
    payment_mode:str|None=Query(default=None,pattern=r"^(cash|upi|bank|cheque)$"),
    user:User=Depends(require_owner),db:AsyncSession=Depends(get_db),
):
    company=await require_company(db,user.id);rows=[]
    payments=(await db.execute(select(ChitPayment,ChitEnrollment,ChitSchedule,ChitGroup,Member).join(ChitEnrollment,ChitPayment.enrollment_id==ChitEnrollment.id).join(ChitSchedule,ChitPayment.schedule_id==ChitSchedule.id).join(ChitGroup,ChitEnrollment.group_id==ChitGroup.id).join(Member,ChitEnrollment.member_id==Member.id).where(ChitGroup.company_id==company.id,ChitPayment.status!="reversed",ChitPayment.payment_source!="advance"))).all()
    for payment,enrollment,schedule,group,member in payments:
        rows.append({"id":f"collection-{payment.id}","transaction_type":"collection","direction":"inflow","transaction_date":payment.payment_date,"reference_number":payment.receipt_number or payment.reference_number,"scheme_id":group.id,"scheme_name":group.scheme_name,"member_id":member.id,"member_name":member.full_name,"description":f"Installment #{schedule.installment_number}","payment_mode":payment.payment_mode,"amount":payment.received_amount,"status":payment.status})
    advances=(await db.execute(select(AdvancePayment,ChitEnrollment,ChitGroup,Member).join(ChitEnrollment,AdvancePayment.enrollment_id==ChitEnrollment.id).join(ChitGroup,AdvancePayment.group_id==ChitGroup.id).join(Member,ChitEnrollment.member_id==Member.id).where(AdvancePayment.company_id==company.id))).all()
    for advance,enrollment,group,member in advances:
        rows.append({"id":f"advance-{advance.id}","transaction_type":"advance","direction":"inflow","transaction_date":advance.payment_date,"reference_number":advance.receipt_number,"scheme_id":group.id,"scheme_name":group.scheme_name,"member_id":member.id,"member_name":member.full_name,"description":f"Advance received · {advance.status.replace('_',' ')}","payment_mode":advance.payment_mode,"amount":advance.amount,"status":advance.status})
    refunds=(await db.execute(select(PaymentRefund,ChitPayment,ChitEnrollment,ChitGroup,Member).join(ChitPayment,PaymentRefund.payment_id==ChitPayment.id).join(ChitEnrollment,ChitPayment.enrollment_id==ChitEnrollment.id).join(ChitGroup,ChitEnrollment.group_id==ChitGroup.id).join(Member,ChitEnrollment.member_id==Member.id).where(ChitGroup.company_id==company.id,PaymentRefund.status=="posted"))).all()
    for refund,payment,enrollment,group,member in refunds:
        rows.append({"id":f"refund-{refund.id}","transaction_type":"refund","direction":"outflow","transaction_date":refund.refund_date,"reference_number":refund.refund_number,"scheme_id":group.id,"scheme_name":group.scheme_name,"member_id":member.id,"member_name":member.full_name,"description":refund.reason,"payment_mode":refund.refund_mode,"amount":refund.amount,"status":refund.status})
    auctions=(await db.execute(select(ChitAuction,ChitGroup,Member).join(ChitGroup,ChitAuction.group_id==ChitGroup.id).join(ChitEnrollment,ChitAuction.winner_enrollment_id==ChitEnrollment.id).join(Member,ChitEnrollment.member_id==Member.id).where(ChitGroup.company_id==company.id,ChitAuction.status=="paid"))).all()
    for auction,group,member in auctions:
        rows.append({"id":f"auction-{auction.id}","transaction_type":"auction_payout","direction":"outflow","transaction_date":auction.payout_date or auction.auction_date,"reference_number":auction.voucher_number or auction.payout_reference_number,"scheme_id":group.id,"scheme_name":group.scheme_name,"member_id":member.id,"member_name":member.full_name,"description":"Auction winner net payout","payment_mode":auction.payout_mode,"amount":auction.net_payout_amount,"status":auction.status})
    payrolls=list((await db.execute(select(PayrollRun).where(PayrollRun.company_id==company.id,PayrollRun.status=="paid"))).scalars().all())
    for payroll in payrolls:
        rows.append({"id":f"payroll-{payroll.id}","transaction_type":"payroll","direction":"outflow","transaction_date":payroll.payment_date or payroll.period_end,"reference_number":payroll.voucher_number or payroll.payment_reference_number,"scheme_id":None,"scheme_name":None,"member_id":None,"member_name":None,"description":f"Payroll {payroll.payroll_month:02d}/{payroll.payroll_year} · {payroll.employee_count} employees","payment_mode":payroll.payment_mode,"amount":payroll.total_net_salary,"status":payroll.status})
    if date_from:rows=[row for row in rows if row["transaction_date"]>=date_from]
    if date_to:rows=[row for row in rows if row["transaction_date"]<=date_to]
    if transaction_type:rows=[row for row in rows if row["transaction_type"]==transaction_type]
    if scheme_id:rows=[row for row in rows if row["scheme_id"]==scheme_id]
    if member_id:rows=[row for row in rows if row["member_id"]==member_id]
    if payment_mode:rows=[row for row in rows if row["payment_mode"]==payment_mode]
    rows.sort(key=lambda row:(row["transaction_date"],row["id"]),reverse=True);inflow=sum((row["amount"] for row in rows if row["direction"]=="inflow"),Decimal("0"));outflow=sum((row["amount"] for row in rows if row["direction"]=="outflow"),Decimal("0"));by_type={}
    for row in rows:
        item=by_type.setdefault(row["transaction_type"],{"count":0,"amount":Decimal("0")});item["count"]+=1;item["amount"]+=row["amount"]
    return {"rows":rows,"total_inflow":inflow,"total_outflow":outflow,"net_cash_flow":inflow-outflow,"transaction_count":len(rows),"type_summary":[{"transaction_type":key,**value} for key,value in sorted(by_type.items())]}


@router.get("")
async def dashboard_summary(user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);today=date.today();month_start=today.replace(day=1)
    today_collected=await db.scalar(select(func.coalesce(func.sum(ChitPayment.received_amount-ChitPayment.refunded_amount),0)).join(ChitEnrollment).join(ChitGroup).where(ChitGroup.company_id==company.id,ChitPayment.payment_date==today,ChitPayment.status!="reversed"))
    month_collected=await db.scalar(select(func.coalesce(func.sum(ChitPayment.received_amount-ChitPayment.refunded_amount),0)).join(ChitEnrollment).join(ChitGroup).where(ChitGroup.company_id==company.id,ChitPayment.payment_date>=month_start,ChitPayment.status!="reversed"))
    active_members=await db.scalar(select(func.count(Member.id)).where(Member.company_id==company.id,Member.is_active.is_(True)));pending_kyc=await db.scalar(select(func.count(Member.id)).where(Member.company_id==company.id,Member.is_active.is_(True),Member.kyc_status=="pending"))
    active_groups=await db.scalar(select(func.count(ChitGroup.id)).where(ChitGroup.company_id==company.id,ChitGroup.status=="active"));scheme_value=await db.scalar(select(func.coalesce(func.sum(ChitGroup.scheme_amount),0)).where(ChitGroup.company_id==company.id,ChitGroup.status=="active"))
    upcoming=await db.scalar(select(func.count(ChitAuction.id)).join(ChitGroup).where(ChitGroup.company_id==company.id,ChitAuction.status.in_(["pending","approved"])))
    recent=(await db.execute(select(ChitPayment,Member,ChitGroup).join(ChitEnrollment,ChitPayment.enrollment_id==ChitEnrollment.id).join(Member,ChitEnrollment.member_id==Member.id).join(ChitGroup,ChitEnrollment.group_id==ChitGroup.id).where(ChitGroup.company_id==company.id).order_by(ChitPayment.created_at.desc()).limit(8))).all()
    daily=[]
    for offset in range(13,-1,-1):
        day=today-timedelta(days=offset);amount=await db.scalar(select(func.coalesce(func.sum(ChitPayment.received_amount-ChitPayment.refunded_amount),0)).join(ChitEnrollment).join(ChitGroup).where(ChitGroup.company_id==company.id,ChitPayment.payment_date==day,ChitPayment.status!="reversed"));daily.append({"date":day,"amount":amount})
    return {"today_collections":today_collected,"month_collections":month_collected,"active_members":active_members,"pending_kyc":pending_kyc,"active_groups":active_groups,"active_scheme_value":scheme_value,"upcoming_auctions":upcoming,"daily_collections":daily,"recent_collections":[{"payment_id":payment.id,"receipt_number":payment.receipt_number,"member_name":member.full_name,"scheme_name":group.scheme_name,"group_code":group.group_code,"amount":payment.received_amount-payment.refunded_amount,"payment_mode":payment.payment_mode,"status":payment.status} for payment,member,group in recent]}
