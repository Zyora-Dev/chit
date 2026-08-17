from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import require_owner
from app.api.routes.members import require_company
from app.db.session import get_db
from app.models.advance import AdvanceAllocation, AdvancePayment
from app.models.chit import ChitAuction, ChitEnrollment, ChitGroup, ChitPayment, ChitSchedule
from app.models.member import Member
from app.models.user import User
from app.schemas.advance import AdvanceAllocate, AdvancePaymentCreate, AdvancePaymentResponse
from app.services.accounting import document_number, post_entries, validate_branch
from app.services.audit import add_audit
from app.services.communications import add_notification,notify_payment_collection

router = APIRouter(prefix="/api/v1/advance-payments", tags=["Advance Payments"])


async def serialize_advance(db: AsyncSession, advance: AdvancePayment):
    enrollment = await db.get(ChitEnrollment, advance.enrollment_id)
    group, member = await db.get(ChitGroup, advance.group_id), await db.get(Member, enrollment.member_id)
    return {"id": advance.id, "group_id": group.id, "group_code": group.group_code, "scheme_name": group.scheme_name, "member_id": member.id, "member_code": member.member_code, "member_name": member.full_name, "mobile_number": member.mobile_number, "receipt_number": advance.receipt_number, "amount": advance.amount, "allocated_amount": advance.allocated_amount, "available_amount": advance.amount - advance.allocated_amount, "payment_date": advance.payment_date, "payment_mode": advance.payment_mode, "reference_number": advance.reference_number, "status": advance.status, "created_at": advance.created_at}


@router.post("", response_model=AdvancePaymentResponse, status_code=201)
async def create_advance(payload: AdvancePaymentCreate, request: Request, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id)
    group = await db.scalar(select(ChitGroup).where(ChitGroup.id == payload.group_id, ChitGroup.company_id == company.id).options(selectinload(ChitGroup.enrollments)))
    if not group: raise HTTPException(status_code=404, detail="Scheme not found")
    enrollment = next((item for item in group.enrollments if item.member_id == payload.member_id and item.status == "active"), None)
    if not enrollment: raise HTTPException(status_code=400, detail="Member is not actively enrolled in this scheme")
    try: await validate_branch(db, company.id, payload.branch_id)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
    receipt_number = document_number("ADV", company.company_code, payload.payment_date)
    advance = AdvancePayment(company_id=company.id, group_id=group.id, enrollment_id=enrollment.id, branch_id=payload.branch_id, receipt_number=receipt_number, amount=payload.amount, allocated_amount=0, payment_date=payload.payment_date, payment_mode=payload.payment_mode, reference_number=payload.reference_number, notes=payload.notes, received_by_user_id=user.id)
    db.add(advance); await db.flush()
    cash_account = "cash_on_hand" if payload.payment_mode == "cash" else "bank_clearing"
    post_entries(db, company_id=company.id, branch_id=payload.branch_id, group_id=group.id, member_id=payload.member_id, source_type="advance_payment", source_id=advance.id, entry_date=payload.payment_date, reference_number=receipt_number, posted_by_user_id=user.id, entries=[("debit", cash_account, payload.amount, "Advance payment received"), ("credit", "member_advance_liability", payload.amount, "Member advance balance")])
    add_audit(db, company_id=company.id, user_id=user.id, action="create", entity_type="advance_payment", entity_id=advance.id, description=f"Advance payment {receipt_number} received", request=request, new_values={"amount": str(payload.amount), "member_id": payload.member_id, "group_id": group.id})
    member=await db.get(Member,enrollment.member_id);add_notification(db,company_id=company.id,user_id=company.owner_id,title=f"Advance collected · {member.full_name}",message=f"₹{payload.amount} received for {group.scheme_name} via {payload.payment_mode.upper()} · {receipt_number}",notification_type="payment",href="/dashboard/advance-payments",entity_type="advance_payment",entity_id=advance.id)
    await db.commit();await notify_payment_collection(db,company=company,member_name=member.full_name,scheme_name=group.scheme_name,amount=payload.amount,receipt_number=receipt_number,payment_mode=payload.payment_mode,source="advance",entity_id=advance.id,add_in_app=False); await db.refresh(advance)
    return await serialize_advance(db, advance)


@router.get("", response_model=list[AdvancePaymentResponse])
async def list_advances(
    group_id: int | None = None, member_id: int | None = None,
    payment_status: str | None = None, date_from: date | None = None, date_to: date | None = None,
    user: User = Depends(require_owner), db: AsyncSession = Depends(get_db),
):
    company = await require_company(db, user.id)
    query = select(AdvancePayment).where(AdvancePayment.company_id == company.id)
    if group_id: query = query.where(AdvancePayment.group_id == group_id)
    if member_id: query = query.join(ChitEnrollment).where(ChitEnrollment.member_id == member_id)
    if payment_status: query = query.where(AdvancePayment.status == payment_status)
    if date_from: query = query.where(AdvancePayment.payment_date >= date_from)
    if date_to: query = query.where(AdvancePayment.payment_date <= date_to)
    advances = (await db.execute(query.order_by(AdvancePayment.created_at.desc()))).scalars().all()
    return [await serialize_advance(db, advance) for advance in advances]


@router.get("/{advance_id}", response_model=AdvancePaymentResponse)
async def get_advance(advance_id: int, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id)
    advance = await db.scalar(select(AdvancePayment).where(AdvancePayment.id == advance_id, AdvancePayment.company_id == company.id))
    if not advance:
        raise HTTPException(status_code=404, detail="Advance payment not found")
    return await serialize_advance(db, advance)


@router.post("/{advance_id}/allocate", response_model=AdvancePaymentResponse)
async def allocate_advance(advance_id: int, payload: AdvanceAllocate, request: Request, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id)
    advance = await db.scalar(select(AdvancePayment).where(AdvancePayment.id == advance_id, AdvancePayment.company_id == company.id))
    if not advance: raise HTTPException(status_code=404, detail="Advance payment not found")
    available = advance.amount - advance.allocated_amount
    if available <= 0: raise HTTPException(status_code=409, detail="Advance payment is fully allocated")
    enrollment = await db.get(ChitEnrollment, advance.enrollment_id)
    schedules = list((await db.execute(select(ChitSchedule).where(ChitSchedule.group_id == advance.group_id).order_by(ChitSchedule.installment_number))).scalars().all())
    if payload.schedule_ids is not None:
        requested = set(payload.schedule_ids)
        if not requested:
            raise HTTPException(status_code=400, detail="Select at least one installment or use automatic allocation")
        schedules = [row for row in schedules if row.id in requested]
        if {row.id for row in schedules} != requested:
            raise HTTPException(status_code=400, detail="One or more selected installments are invalid")
    allocated = Decimal("0")
    for schedule in schedules:
        if available <= 0: break
        if schedule.installment_number < enrollment.start_installment or (enrollment.end_installment and schedule.installment_number > enrollment.end_installment): continue
        if await db.scalar(select(ChitAuction.id).where(ChitAuction.winner_enrollment_id == enrollment.id, ChitAuction.schedule_id == schedule.id)): continue
        paid = await db.scalar(select(func.coalesce(func.sum(ChitPayment.amount), 0)).where(ChitPayment.enrollment_id == enrollment.id, ChitPayment.schedule_id == schedule.id, ChitPayment.status == "posted"))
        balance = schedule.payable_amount - Decimal(paid)
        if balance <= 0: continue
        amount = min(balance, available); receipt = document_number("RCP", company.company_code, advance.payment_date)
        payment = ChitPayment(enrollment_id=enrollment.id, schedule_id=schedule.id, amount=amount, received_amount=amount, payment_date=advance.payment_date, payment_mode=advance.payment_mode, reference_number=advance.receipt_number, notes=f"Allocated from advance {advance.receipt_number}", receipt_number=receipt, branch_id=advance.branch_id, collected_by_user_id=user.id, payment_source="advance", status="posted")
        db.add(payment); await db.flush(); db.add(AdvanceAllocation(advance_payment_id=advance.id, payment_id=payment.id, schedule_id=schedule.id, amount=amount, allocated_by_user_id=user.id))
        post_entries(db, company_id=company.id, branch_id=advance.branch_id, group_id=advance.group_id, member_id=enrollment.member_id, source_type="advance_allocation", source_id=payment.id, entry_date=advance.payment_date, reference_number=receipt, posted_by_user_id=user.id, entries=[("debit", "member_advance_liability", amount, f"Advance allocated to installment #{schedule.installment_number}"), ("credit", "member_installment_receivable", amount, f"Installment #{schedule.installment_number} paid from advance")])
        available -= amount; allocated += amount
    if allocated <= 0: raise HTTPException(status_code=409, detail="No eligible installment balance found")
    advance.allocated_amount += allocated; advance.status = "allocated" if advance.allocated_amount == advance.amount else "partially_allocated"
    add_audit(db, company_id=company.id, user_id=user.id, action="allocate", entity_type="advance_payment", entity_id=advance.id, description=f"Allocated {allocated} from advance {advance.receipt_number}", request=request, old_values={"allocated_amount": str(advance.allocated_amount - allocated)}, new_values={"allocated_amount": str(advance.allocated_amount)})
    await db.commit(); await db.refresh(advance)
    return await serialize_advance(db, advance)
