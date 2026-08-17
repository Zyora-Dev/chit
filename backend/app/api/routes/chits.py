import calendar
import csv
import io
import secrets
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import require_owner
from app.api.routes.members import require_company, save_document
from app.core.config import settings
from app.db.session import get_db
from app.models.chit import AuctionBid, ChitAuction, ChitEnrollment, ChitEnrollmentTransfer, ChitGroup, ChitGroupClosure, ChitPayment, ChitSchedule, LedgerEntry, PaymentRefund
from app.models.company import Company
from app.models.branch import Branch
from app.models.member import Member
from app.models.user import User
from app.schemas.chit import AuctionApproval, AuctionBidCreate, AuctionCreate, AuctionPayout, AuctionResponse, AuctionVoucherResponse, CancellationCreate, ChitCreate, ChitDetailResponse, ChitResponse, CollectionReportResponse, EnrollmentReplace, EnrollmentTransferApproval, EnrollmentTransferResponse, EnrollmentUpdate, LedgerEntryResponse, MemberLedgerResponse, PaymentCreate, PaymentReceiptResponse, RefundCreate, ReversalCreate, ScheduleBulkUpdate, SchemeClose
from app.services.accounting import document_number, post_entries, reverse_entries, validate_branch
from app.services.audit import add_audit
from app.services.communications import add_notification,notify_payment_collection

router = APIRouter(prefix="/api/v1/chits", tags=["Chit Groups"])


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year, month = value.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


async def load_group(db: AsyncSession, group_id: int, company_id: int) -> ChitGroup:
    result = await db.execute(
        select(ChitGroup)
        .where(ChitGroup.id == group_id, ChitGroup.company_id == company_id)
        .options(selectinload(ChitGroup.schedules), selectinload(ChitGroup.enrollments))
        .execution_options(populate_existing=True)
    )
    group = result.scalar_one_or_none()
    if not group: raise HTTPException(status_code=404, detail="Chit group not found")
    return group


async def serialize_group(db: AsyncSession, group: ChitGroup, include_payments: bool = False):
    member_ids = [item.member_id for item in group.enrollments]
    members = (await db.execute(select(Member).where(Member.id.in_(member_ids)))).scalars().all() if member_ids else []
    member_map = {m.id: m for m in members}
    enrolled = [{"enrollment_id": e.id, "member_id": e.member_id, "member_code": member_map[e.member_id].member_code, "full_name": member_map[e.member_id].full_name, "mobile_number": member_map[e.member_id].mobile_number, "start_installment": e.start_installment, "end_installment": e.end_installment, "status": e.status, "replaced_enrollment_id": e.replaced_enrollment_id, "break_reason": e.break_reason} for e in group.enrollments]
    active_count = sum(1 for enrollment in group.enrollments if enrollment.status == "active")
    data = {"id": group.id, "group_code": group.group_code, "scheme_name": group.scheme_name, "scheme_amount": group.scheme_amount, "start_date": group.start_date, "duration_months": group.duration_months, "max_member_count": group.max_member_count, "active_member_count": active_count, "available_slot_count": max(group.max_member_count - active_count, 0), "foreman_commission_percent": group.foreman_commission_percent, "maturity_date": group.maturity_date, "grace_period_days": group.grace_period_days, "late_fee_type": group.late_fee_type, "late_fee_value": group.late_fee_value, "auction_weekday":group.auction_weekday,"auction_time":group.auction_time,"minimum_discount_percent":group.minimum_discount_percent,"maximum_discount_percent":group.maximum_discount_percent,"status": group.status, "schedules": sorted(group.schedules, key=lambda x: x.installment_number), "members": enrolled, "created_at": group.created_at}
    if include_payments:
        schedule_map = {s.id: s for s in group.schedules}; enrollment_map = {e.id: e for e in group.enrollments}
        payments = (await db.execute(select(ChitPayment).where(ChitPayment.enrollment_id.in_(list(enrollment_map))))).scalars().all() if enrollment_map else []
        data["payments"] = [{"id": p.id, "member_id": enrollment_map[p.enrollment_id].member_id, "member_name": member_map[enrollment_map[p.enrollment_id].member_id].full_name, "schedule_id": p.schedule_id, "installment_number": schedule_map[p.schedule_id].installment_number, "amount": p.amount, "received_amount": p.received_amount, "late_fee_amount": p.late_fee_amount, "penalty_amount": p.penalty_amount, "waiver_amount": p.waiver_amount, "excess_amount": p.excess_amount, "refunded_amount": p.refunded_amount, "payment_date": p.payment_date, "payment_mode": p.payment_mode, "reference_number": p.reference_number, "receipt_number": p.receipt_number, "branch_id": p.branch_id, "payment_source": p.payment_source, "status": p.status} for p in payments]
        auctions = (await db.execute(select(ChitAuction).where(ChitAuction.group_id == group.id))).scalars().all()
        data["auctions"] = [serialize_auction(a, group, schedule_map, enrollment_map, member_map) for a in auctions]
    return data


def serialize_auction(auction, group, schedule_map, enrollment_map, member_map):
    schedule = schedule_map[auction.schedule_id]; enrollment = enrollment_map[auction.winner_enrollment_id]; member = member_map[enrollment.member_id]
    return {"id": auction.id, "group_id": group.id, "group_code": group.group_code, "scheme_name": group.scheme_name, "schedule_id": schedule.id, "installment_number": schedule.installment_number, "due_date": schedule.due_date, "winner_member_id": member.id, "winner_name": member.full_name, "auction_date": auction.auction_date, "bid_amount": auction.bid_amount, "discount_amount": auction.discount_amount, "commission_amount": auction.commission_amount, "commission_percent": auction.commission_percent, "payout_amount": auction.payout_amount, "settled_installment_amount": auction.settled_installment_amount, "net_payout_amount": auction.net_payout_amount, "status": auction.status, "notes": auction.notes, "voucher_number": auction.voucher_number, "branch_id": auction.branch_id, "winner_acknowledged_at": auction.winner_acknowledged_at, "approved_at": auction.approved_at, "approval_notes": auction.approval_notes, "payout_date": auction.payout_date, "payout_mode": auction.payout_mode, "payout_reference_number": auction.payout_reference_number, "payout_verified_at": auction.payout_verified_at, "settlement_proof_file_name": auction.settlement_proof_file_name}


@router.post("", response_model=ChitResponse, status_code=201)
async def create_chit(payload: ChitCreate, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id)
    if payload.minimum_discount_percent>payload.maximum_discount_percent: raise HTTPException(status_code=400,detail="Minimum discount cannot exceed maximum discount")
    group = ChitGroup(company_id=company.id, group_code=f"CHT-{secrets.token_hex(4).upper()}", scheme_name=payload.scheme_name.strip(), scheme_amount=payload.scheme_amount, start_date=payload.start_date, duration_months=payload.duration_months, max_member_count=payload.max_member_count or payload.duration_months, foreman_commission_percent=payload.foreman_commission_percent, maturity_date=add_months(payload.start_date, payload.duration_months - 1), grace_period_days=payload.grace_period_days, late_fee_type=payload.late_fee_type, late_fee_value=payload.late_fee_value,auction_weekday=payload.auction_weekday,auction_time=payload.auction_time,minimum_discount_percent=payload.minimum_discount_percent,maximum_discount_percent=payload.maximum_discount_percent)
    installment = (payload.scheme_amount / payload.duration_months).quantize(Decimal("0.01"))
    group.schedules = [ChitSchedule(installment_number=i + 1, due_date=add_months(payload.start_date, i), installment_amount=installment, dividend=0, payable_amount=installment, receivable_amount=0) for i in range(payload.duration_months)]
    db.add(group)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Unable to generate a unique scheme code. Please try again.") from exc
    group = await load_group(db, group.id, company.id)
    return await serialize_group(db, group)


@router.get("", response_model=list[ChitResponse])
async def list_chits(user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id)
    groups = (await db.execute(select(ChitGroup).where(ChitGroup.company_id == company.id).order_by(ChitGroup.created_at.desc()).options(selectinload(ChitGroup.schedules), selectinload(ChitGroup.enrollments)))).scalars().all()
    return [await serialize_group(db, group) for group in groups]


@router.get("/auctions/all", response_model=list[AuctionResponse])
async def list_all_auctions(
    scheme_id: int | None = None, member_id: int | None = None,
    date_from: date | None = None, date_to: date | None = None,
    auction_status: str | None = Query(default=None, alias="status", max_length=30),
    user: User = Depends(require_owner), db: AsyncSession = Depends(get_db),
):
    company = await require_company(db, user.id)
    group_query = select(ChitGroup).where(ChitGroup.company_id == company.id)
    if scheme_id is not None:
        group_query = group_query.where(ChitGroup.id == scheme_id)
    groups = (await db.execute(group_query.options(selectinload(ChitGroup.schedules), selectinload(ChitGroup.enrollments)))).scalars().all()
    result = []
    for group in groups:
        detail = await serialize_group(db, group, True)
        result.extend(detail["auctions"])
    if member_id is not None:
        result = [row for row in result if row["winner_member_id"] == member_id]
    if date_from is not None:
        result = [row for row in result if row["auction_date"] >= date_from]
    if date_to is not None:
        result = [row for row in result if row["auction_date"] <= date_to]
    if auction_status is not None:
        result = [row for row in result if row["status"] == auction_status]
    return sorted(result, key=lambda row: row["auction_date"], reverse=True)


@router.get("/collections/report", response_model=CollectionReportResponse)
async def collection_report(
    scheme_id: int | None = None, member_id: int | None = None,
    date_from: date | None = None, date_to: date | None = None,
    payment_mode: str | None = Query(default=None, pattern=r"^(cash|upi|bank|cheque)$"),
    payment_status: str | None = Query(default=None, alias="status", max_length=30),
    user: User = Depends(require_owner), db: AsyncSession = Depends(get_db),
):
    company = await require_company(db, user.id)
    query = (
        select(ChitPayment, ChitEnrollment, ChitSchedule, ChitGroup, Member, Branch, User.email)
        .join(ChitEnrollment, ChitPayment.enrollment_id == ChitEnrollment.id)
        .join(ChitSchedule, ChitPayment.schedule_id == ChitSchedule.id)
        .join(ChitGroup, ChitEnrollment.group_id == ChitGroup.id)
        .join(Member, ChitEnrollment.member_id == Member.id)
        .outerjoin(Branch, ChitPayment.branch_id == Branch.id)
        .outerjoin(User, ChitPayment.collected_by_user_id == User.id)
        .where(ChitGroup.company_id == company.id)
    )
    if scheme_id is not None: query = query.where(ChitGroup.id == scheme_id)
    if member_id is not None: query = query.where(Member.id == member_id)
    if date_from is not None: query = query.where(ChitPayment.payment_date >= date_from)
    if date_to is not None: query = query.where(ChitPayment.payment_date <= date_to)
    if payment_mode is not None: query = query.where(ChitPayment.payment_mode == payment_mode)
    if payment_status is not None: query = query.where(ChitPayment.status == payment_status)
    records = (await db.execute(query.order_by(ChitPayment.payment_date.desc(), ChitPayment.created_at.desc()))).all()
    rows = [{"payment_id": payment.id, "payment_date": payment.payment_date, "amount": payment.amount, "received_amount":payment.received_amount, "late_fee_amount":payment.late_fee_amount, "penalty_amount":payment.penalty_amount, "waiver_amount":payment.waiver_amount, "waiver_reason":payment.waiver_reason, "excess_amount":payment.excess_amount, "refunded_amount":payment.refunded_amount, "net_received_amount":payment.received_amount-payment.refunded_amount, "payment_mode": payment.payment_mode, "reference_number": payment.reference_number, "notes": payment.notes, "group_id": group.id, "group_code": group.group_code, "scheme_name": group.scheme_name, "member_id": member.id, "member_code": member.member_code, "member_name": member.full_name, "mobile_number": member.mobile_number, "installment_number": schedule.installment_number, "due_date": schedule.due_date, "payable_amount": schedule.payable_amount, "receipt_number": payment.receipt_number, "status": payment.status, "branch_id":payment.branch_id, "branch_code":branch.branch_code if branch else None, "branch_name":branch.name if branch else None, "collected_by_user_id":payment.collected_by_user_id, "collector_email":collector_email, "payment_source":payment.payment_source, "collection_location_text":payment.collection_location_text, "collection_latitude":payment.collection_latitude, "collection_longitude":payment.collection_longitude} for payment, enrollment, schedule, group, member, branch, collector_email in records]
    mode_totals, daily_totals = {}, {}
    for row in rows:
        mode = mode_totals.setdefault(row["payment_mode"], {"count": 0, "amount": Decimal("0")}); mode["count"] += 1; mode["amount"] += row["amount"]
        daily = daily_totals.setdefault(row["payment_date"], {"count": 0, "amount": Decimal("0")}); daily["count"] += 1; daily["amount"] += row["amount"]
    return {"rows": rows, "total_amount": sum((row["amount"] for row in rows), Decimal("0")), "total_received_amount":sum((row["received_amount"] for row in rows),Decimal("0")), "total_refunded_amount":sum((row["refunded_amount"] for row in rows),Decimal("0")), "net_received_amount":sum((row["net_received_amount"] for row in rows),Decimal("0")), "total_transactions": len(rows), "unique_members": len({row["member_id"] for row in rows}), "schemes_count": len({row["group_id"] for row in rows}), "mode_summary": [{"payment_mode": mode, **values} for mode, values in sorted(mode_totals.items())], "daily_summary": [{"date": day, **values} for day, values in sorted(daily_totals.items())]}


def company_address(company: Company) -> str | None:
    if not company.addresses:
        return None
    address = company.addresses[0]
    return ", ".join(filter(None, [address.address_line_1, address.address_line_2, address.locality, address.city, address.state, address.postal_code]))


@router.get("/receipts/payments/{payment_id}", response_model=PaymentReceiptResponse)
async def payment_receipt(payment_id: int, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id)
    record = (
        await db.execute(
            select(ChitPayment, ChitEnrollment, ChitSchedule, ChitGroup, Member)
            .join(ChitEnrollment, ChitPayment.enrollment_id == ChitEnrollment.id)
            .join(ChitSchedule, ChitPayment.schedule_id == ChitSchedule.id)
            .join(ChitGroup, ChitEnrollment.group_id == ChitGroup.id)
            .join(Member, ChitEnrollment.member_id == Member.id)
            .where(ChitPayment.id == payment_id, ChitGroup.company_id == company.id)
        )
    ).one_or_none()
    if record is None: raise HTTPException(status_code=404, detail="Payment receipt not found")
    payment, enrollment, schedule, group, member = record
    total_paid = await db.scalar(select(func.coalesce(func.sum(ChitPayment.amount), 0)).where(ChitPayment.enrollment_id == enrollment.id, ChitPayment.schedule_id == schedule.id, ChitPayment.status == "posted"))
    payment_data = {"id": payment.id, "member_id": member.id, "member_name": member.full_name, "schedule_id": schedule.id, "installment_number": schedule.installment_number, "amount": payment.amount, "received_amount":payment.received_amount, "late_fee_amount":payment.late_fee_amount, "penalty_amount":payment.penalty_amount, "waiver_amount":payment.waiver_amount, "excess_amount":payment.excess_amount, "refunded_amount":payment.refunded_amount, "payment_date": payment.payment_date, "payment_mode": payment.payment_mode, "reference_number": payment.reference_number, "receipt_number": payment.receipt_number, "branch_id": payment.branch_id, "payment_source": payment.payment_source, "status": payment.status}
    return {"payment": payment_data, "company_name": company.name, "company_code": company.company_code, "company_address": company_address(company), "scheme_name": group.scheme_name, "group_code": group.group_code, "member_name": member.full_name, "member_code": member.member_code, "mobile_number": member.mobile_number, "installment_number": schedule.installment_number, "due_date": schedule.due_date, "payable_amount": schedule.payable_amount, "total_paid": total_paid, "balance_amount": max(schedule.payable_amount - Decimal(total_paid), Decimal("0"))}


@router.get("/vouchers/auctions/{auction_id}", response_model=AuctionVoucherResponse)
async def auction_voucher(auction_id: int, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id)
    record = (
        await db.execute(
            select(ChitAuction, ChitEnrollment, ChitSchedule, ChitGroup, Member)
            .join(ChitEnrollment, ChitAuction.winner_enrollment_id == ChitEnrollment.id)
            .join(ChitSchedule, ChitAuction.schedule_id == ChitSchedule.id)
            .join(ChitGroup, ChitAuction.group_id == ChitGroup.id)
            .join(Member, ChitEnrollment.member_id == Member.id)
            .where(ChitAuction.id == auction_id, ChitGroup.company_id == company.id)
        )
    ).one_or_none()
    if record is None: raise HTTPException(status_code=404, detail="Auction voucher not found")
    auction, enrollment, schedule, group, member = record
    auction_data = serialize_auction(auction, group, {schedule.id: schedule}, {enrollment.id: enrollment}, {member.id: member})
    return {"auction": auction_data, "company_name": company.name, "company_code": company.company_code, "company_address": company_address(company), "member_code": member.member_code, "mobile_number": member.mobile_number}


@router.get("/ledger/entries", response_model=list[LedgerEntryResponse])
async def ledger_entries(
    scheme_id: int | None = None, member_id: int | None = None,
    date_from: date | None = None, date_to: date | None = None,
    user: User = Depends(require_owner), db: AsyncSession = Depends(get_db),
):
    company = await require_company(db, user.id)
    query = select(LedgerEntry).where(LedgerEntry.company_id == company.id)
    if scheme_id is not None: query = query.where(LedgerEntry.group_id == scheme_id)
    if member_id is not None: query = query.where(LedgerEntry.member_id == member_id)
    if date_from is not None: query = query.where(LedgerEntry.entry_date >= date_from)
    if date_to is not None: query = query.where(LedgerEntry.entry_date <= date_to)
    return list((await db.execute(query.order_by(LedgerEntry.entry_date.desc(), LedgerEntry.id.desc()))).scalars().all())


@router.post("/receipts/payments/{payment_id}/reverse", response_model=PaymentReceiptResponse)
async def reverse_payment(payment_id: int, payload: ReversalCreate, request: Request, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id)
    payment = await db.scalar(select(ChitPayment).join(ChitEnrollment).join(ChitGroup).where(ChitPayment.id == payment_id, ChitGroup.company_id == company.id))
    if payment is None: raise HTTPException(status_code=404, detail="Payment not found")
    if payment.status == "reversed": raise HTTPException(status_code=409, detail="Payment is already reversed")
    try: await reverse_entries(db, source_type="payment", source_id=payment.id, reason=payload.reason, posted_by_user_id=user.id, reversal_date=date.today())
    except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc
    payment.status = "reversed"; payment.reversed_at = datetime.now(UTC); payment.reversal_reason = payload.reason; payment.reversed_by_user_id = user.id
    add_audit(db, company_id=company.id, user_id=user.id, action="reverse", entity_type="payment", entity_id=payment.id, description=f"Reversed payment {payment.receipt_number}", request=request, old_values={"status": "posted"}, new_values={"status": "reversed", "reason": payload.reason})
    await db.commit()
    return await payment_receipt(payment.id, user, db)


@router.post("/vouchers/auctions/{auction_id}/reverse", response_model=AuctionVoucherResponse)
async def reverse_auction(auction_id: int, payload: ReversalCreate, request: Request, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id)
    auction = await db.scalar(select(ChitAuction).join(ChitGroup).where(ChitAuction.id == auction_id, ChitGroup.company_id == company.id))
    if auction is None: raise HTTPException(status_code=404, detail="Auction not found")
    if auction.status != "paid": raise HTTPException(status_code=409, detail="Only paid auctions can be reversed")
    try: await reverse_entries(db, source_type="auction", source_id=auction.id, reason=payload.reason, posted_by_user_id=user.id, reversal_date=date.today())
    except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc
    auction.status = "reversed"; auction.reversed_at = datetime.now(UTC); auction.reversal_reason = payload.reason; auction.reversed_by_user_id = user.id
    add_audit(db, company_id=company.id, user_id=user.id, action="reverse", entity_type="auction", entity_id=auction.id, description=f"Reversed auction voucher {auction.voucher_number}", request=request, old_values={"status": "paid"}, new_values={"status": "reversed", "reason": payload.reason})
    await db.commit()
    return await auction_voucher(auction.id, user, db)


@router.post("/{group_id}/auctions/{auction_id}/approve", response_model=ChitDetailResponse)
async def approve_auction(group_id: int, auction_id: int, payload: AuctionApproval, request: Request, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id); group = await load_group(db, group_id, company.id)
    auction = await db.scalar(select(ChitAuction).where(ChitAuction.id == auction_id, ChitAuction.group_id == group.id))
    if not auction: raise HTTPException(status_code=404, detail="Auction not found")
    if auction.status != "pending": raise HTTPException(status_code=409, detail="Only pending auctions can be approved")
    if not payload.winner_acknowledged: raise HTTPException(status_code=400, detail="Winner acknowledgement is required")
    now = datetime.now(UTC); auction.winner_acknowledged_at = now; auction.approved_at = now; auction.approved_by_user_id = user.id; auction.approval_notes = payload.approval_notes; auction.status = "approved"
    add_audit(db, company_id=company.id, user_id=user.id, action="approve", entity_type="auction", entity_id=auction.id, description="Approved auction winner", request=request, old_values={"status":"pending"}, new_values={"status":"approved", "winner_acknowledged":True})
    await db.commit(); group = await load_group(db, group_id, company.id); return await serialize_group(db, group, True)


@router.post("/{group_id}/auctions/{auction_id}/pay", response_model=ChitDetailResponse)
async def pay_auction(
    group_id: int, auction_id: int, request: Request,
    payout_date: date = Form(), payout_mode: str = Form(), payout_reference_number: str | None = Form(default=None),
    payout_verified: bool = Form(), settlement_proof: UploadFile = File(),
    user: User = Depends(require_owner), db: AsyncSession = Depends(get_db),
):
    company = await require_company(db, user.id); group = await load_group(db, group_id, company.id)
    auction = await db.scalar(select(ChitAuction).where(ChitAuction.id == auction_id, ChitAuction.group_id == group.id))
    if not auction: raise HTTPException(status_code=404, detail="Auction not found")
    if auction.status != "approved": raise HTTPException(status_code=409, detail="Only approved auctions can be paid")
    if not payout_verified: raise HTTPException(status_code=400, detail="Payout verification is required")
    if payout_mode not in {"cash","upi","bank","cheque"}: raise HTTPException(status_code=400, detail="Invalid payout mode")
    if payout_mode != "cash" and not payout_reference_number: raise HTTPException(status_code=400, detail="Payout reference is required")
    root = Path(settings.upload_directory).resolve() / "private" / "auctions" / company.company_code / str(auction.id)
    proof_path, proof_name = await save_document(settlement_proof, root / "settlement-proof")
    voucher = document_number("AUC", company.company_code, payout_date)
    cash_account = "cash_on_hand" if payout_mode == "cash" else "bank_clearing"
    try:
        post_entries(db, company_id=company.id, branch_id=auction.branch_id, group_id=group.id, member_id=(await db.get(ChitEnrollment, auction.winner_enrollment_id)).member_id, source_type="auction", source_id=auction.id, entry_date=payout_date, reference_number=voucher, posted_by_user_id=user.id, entries=[("debit", "auction_payout_expense", auction.payout_amount, "Auction gross payout"), ("credit", "member_installment_receivable", auction.settled_installment_amount, "Winner installment settled"), ("credit", cash_account, auction.net_payout_amount, "Verified net payout")])
    except ValueError as exc:
        Path(proof_path).unlink(missing_ok=True); await db.rollback(); raise HTTPException(status_code=500, detail=str(exc)) from exc
    now = datetime.now(UTC); auction.status = "paid"; auction.voucher_number = voucher; auction.payout_date = payout_date; auction.payout_mode = payout_mode; auction.payout_reference_number = payout_reference_number; auction.payout_verified_at = now; auction.payout_verified_by_user_id = user.id; auction.settled_by_user_id = user.id; auction.settlement_proof_path = proof_path; auction.settlement_proof_file_name = proof_name
    add_audit(db, company_id=company.id, user_id=user.id, action="pay", entity_type="auction", entity_id=auction.id, description=f"Verified and paid auction {voucher}", request=request, old_values={"status":"approved"}, new_values={"status":"paid", "payout_date":str(payout_date)})
    await db.commit(); group = await load_group(db, group_id, company.id); return await serialize_group(db, group, True)


@router.get("/{group_id}/auctions/{auction_id}/settlement-proof")
async def auction_settlement_proof(group_id: int, auction_id: int, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id)
    auction = await db.scalar(select(ChitAuction).join(ChitGroup).where(ChitAuction.id == auction_id, ChitAuction.group_id == group_id, ChitGroup.company_id == company.id))
    if not auction or not auction.settlement_proof_path or not Path(auction.settlement_proof_path).is_file(): raise HTTPException(status_code=404, detail="Settlement proof not found")
    return FileResponse(auction.settlement_proof_path, filename=auction.settlement_proof_file_name, content_disposition_type="inline")


@router.get("/{group_id}/reconciliation")
async def scheme_reconciliation(group_id: int, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id); group = await load_group(db, group_id, company.id)
    expected = sum(
        (
            schedule.payable_amount
            for enrollment in group.enrollments
            for schedule in group.schedules
            if schedule.installment_number >= enrollment.start_installment
            and (enrollment.end_installment is None or schedule.installment_number <= enrollment.end_installment)
        ),
        Decimal("0"),
    )
    collected = await db.scalar(select(func.coalesce(func.sum(ChitPayment.amount - ChitPayment.refunded_amount), 0)).join(ChitEnrollment).where(ChitEnrollment.group_id == group.id, ChitPayment.status != "reversed"))
    cash_collected = await db.scalar(select(func.coalesce(func.sum(ChitPayment.received_amount - ChitPayment.refunded_amount), 0)).join(ChitEnrollment).where(ChitEnrollment.group_id == group.id, ChitPayment.status != "reversed"))
    settled = await db.scalar(select(func.coalesce(func.sum(ChitAuction.settled_installment_amount), 0)).where(ChitAuction.group_id == group.id, ChitAuction.status == "paid"))
    payouts = await db.scalar(select(func.coalesce(func.sum(ChitAuction.net_payout_amount), 0)).where(ChitAuction.group_id == group.id, ChitAuction.status == "paid"))
    outstanding = max(expected - Decimal(collected) - Decimal(settled), Decimal("0"))
    pending_auctions = await db.scalar(select(func.count(ChitAuction.id)).where(ChitAuction.group_id == group.id, ChitAuction.status.in_(["pending","approved"])))
    expected_closing_balance = Decimal(cash_collected) - Decimal(payouts)
    return {"expected_total":expected, "collected_total":collected, "cash_collected_total":cash_collected, "auction_settled_total":settled, "auction_payout_total":payouts, "outstanding_amount":outstanding, "pending_auctions":pending_auctions, "expected_closing_balance":expected_closing_balance, "can_close":outstanding == 0 and pending_auctions == 0}


@router.post("/{group_id}/close")
async def close_scheme(group_id: int, payload: SchemeClose, request: Request, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id); group = await load_group(db, group_id, company.id)
    if group.status != "active": raise HTTPException(status_code=409, detail="Only active schemes can be closed")
    reconciliation = await scheme_reconciliation(group_id, user, db)
    if not reconciliation["can_close"]: raise HTTPException(status_code=409, detail="Scheme has outstanding collections or unpaid auctions")
    variance = payload.actual_closing_balance - reconciliation["expected_closing_balance"]
    if variance != 0 and not payload.variance_reason: raise HTTPException(status_code=400, detail="Variance reason is required")
    closure = ChitGroupClosure(group_id=group.id, expected_total=reconciliation["expected_total"], collected_total=reconciliation["collected_total"], auction_settled_total=reconciliation["auction_settled_total"], outstanding_amount=reconciliation["outstanding_amount"], expected_closing_balance=reconciliation["expected_closing_balance"], actual_closing_balance=payload.actual_closing_balance, variance_amount=variance, variance_reason=payload.variance_reason, closed_by_user_id=user.id)
    db.add(closure); group.status = "completed"; group.closed_at = datetime.now(UTC); group.closed_by_user_id = user.id
    add_audit(db, company_id=company.id, user_id=user.id, action="close", entity_type="chit_group", entity_id=group.id, description="Closed scheme after final reconciliation", request=request, old_values={"status":"active"}, new_values={"status":"completed", "variance":str(variance)})
    await db.commit(); return {**reconciliation, "status":"completed", "variance_amount":variance}


@router.post("/receipts/payments/{payment_id}/refund")
async def refund_payment(payment_id: int, payload: RefundCreate, request: Request, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id)
    payment = await db.scalar(select(ChitPayment).join(ChitEnrollment).join(ChitGroup).where(ChitPayment.id == payment_id, ChitGroup.company_id == company.id))
    if not payment or payment.status == "reversed": raise HTTPException(status_code=404, detail="Posted payment not found")
    refundable = payment.received_amount - payment.refunded_amount
    if payload.amount > refundable: raise HTTPException(status_code=400, detail=f"Refund exceeds refundable amount of {refundable}")
    refund_number = document_number("REF", company.company_code, payload.refund_date)
    refund = PaymentRefund(payment_id=payment.id, refund_number=refund_number, refund_date=payload.refund_date, amount=payload.amount, refund_mode=payload.refund_mode, reference_number=payload.reference_number, reason=payload.reason, posted_by_user_id=user.id)
    db.add(refund); await db.flush(); enrollment = await db.get(ChitEnrollment, payment.enrollment_id)
    cash_account = "cash_on_hand" if payload.refund_mode == "cash" else "bank_clearing"
    post_entries(db, company_id=company.id, branch_id=payment.branch_id, group_id=enrollment.group_id, member_id=enrollment.member_id, source_type="payment_refund", source_id=refund.id, entry_date=payload.refund_date, reference_number=refund_number, posted_by_user_id=user.id, entries=[("debit", "member_installment_receivable", payload.amount, "Collection refund"), ("credit", cash_account, payload.amount, "Refund paid")])
    payment.refunded_amount += payload.amount; payment.status = "refunded" if payment.refunded_amount == payment.received_amount else "partially_refunded"
    add_audit(db, company_id=company.id, user_id=user.id, action="refund", entity_type="payment", entity_id=payment.id, description=f"Posted refund {refund_number}", request=request, new_values={"amount":str(payload.amount), "status":payment.status})
    await db.commit(); return {"id":refund.id, "refund_number":refund_number, "amount":payload.amount, "payment_status":payment.status}


@router.get("/receipts/payments/{payment_id}/refunds")
async def list_payment_refunds(payment_id:int,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);payment=await db.scalar(select(ChitPayment).join(ChitEnrollment).join(ChitGroup).where(ChitPayment.id==payment_id,ChitGroup.company_id==company.id))
    if not payment: raise HTTPException(status_code=404,detail="Payment not found")
    refunds=(await db.execute(select(PaymentRefund).where(PaymentRefund.payment_id==payment.id).order_by(PaymentRefund.created_at.desc()))).scalars().all();return [{"id":item.id,"refund_number":item.refund_number,"refund_date":item.refund_date,"amount":item.amount,"refund_mode":item.refund_mode,"reference_number":item.reference_number,"reason":item.reason,"status":item.status,"created_at":item.created_at} for item in refunds]


@router.get("/collections/export.csv")
async def export_collections_csv(scheme_id:int|None=None,member_id:int|None=None,date_from:date|None=None,date_to:date|None=None,payment_mode:str|None=None,payment_status:str|None=Query(default=None,alias="status"),user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    report=await collection_report(scheme_id,member_id,date_from,date_to,payment_mode,payment_status,user,db);stream=io.StringIO();writer=csv.writer(stream);writer.writerow(["Date","Receipt","Scheme","Member","Installment","Mode","Principal","Late fee","Penalty","Waiver","Excess","Received","Refunded","Net","Status"])
    for row in report["rows"]: writer.writerow([row["payment_date"],row["receipt_number"],row["scheme_name"],row["member_name"],row["installment_number"],row["payment_mode"],row["amount"],row["late_fee_amount"],row["penalty_amount"],row["waiver_amount"],row["excess_amount"],row["received_amount"],row["refunded_amount"],row["net_received_amount"],row["status"]])
    return StreamingResponse(iter([stream.getvalue()]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=zchit-collections.csv"})


@router.get("/collections/ageing")
async def collection_ageing(as_of: date = date.today(), scheme_id: int | None = None, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id); groups = (await db.execute(select(ChitGroup).where(ChitGroup.company_id == company.id).options(selectinload(ChitGroup.schedules), selectinload(ChitGroup.enrollments)))).scalars().all(); rows = []
    for group in groups:
        if scheme_id and group.id != scheme_id: continue
        member_map = {member.id:member for member in (await db.execute(select(Member).where(Member.id.in_([e.member_id for e in group.enrollments])))).scalars().all()}
        for enrollment in group.enrollments:
            for schedule in group.schedules:
                if schedule.installment_number < enrollment.start_installment or (enrollment.end_installment is not None and schedule.installment_number > enrollment.end_installment): continue
                paid = await db.scalar(select(func.coalesce(func.sum(ChitPayment.amount - ChitPayment.refunded_amount),0)).where(ChitPayment.enrollment_id==enrollment.id, ChitPayment.schedule_id==schedule.id, ChitPayment.status!="reversed")); settled = await db.scalar(select(ChitAuction.id).where(ChitAuction.winner_enrollment_id==enrollment.id, ChitAuction.schedule_id==schedule.id, ChitAuction.status=="paid")); outstanding=max(schedule.payable_amount-Decimal(paid)-(schedule.payable_amount if settled else 0),Decimal("0")); grace_end=add_months(schedule.due_date,0)+timedelta(days=group.grace_period_days)
                if outstanding>0 and grace_end<as_of:
                    days=(as_of-grace_end).days; bucket="1_30" if days<=30 else "31_60" if days<=60 else "61_90" if days<=90 else "91_plus"; member=member_map[enrollment.member_id]; rows.append({"group_id":group.id,"scheme_name":group.scheme_name,"member_id":member.id,"member_name":member.full_name,"member_code":member.member_code,"installment_number":schedule.installment_number,"due_date":schedule.due_date,"days_overdue":days,"ageing_bucket":bucket,"outstanding_amount":outstanding})
    return rows


@router.get("/{group_id}", response_model=ChitDetailResponse)
async def get_chit(group_id: int, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id); group = await load_group(db, group_id, company.id)
    return await serialize_group(db, group, True)


@router.put("/{group_id}/schedule", response_model=ChitResponse)
async def update_schedule(group_id: int, payload: ScheduleBulkUpdate, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id); group = await load_group(db, group_id, company.id)
    if group.status in {"completed", "cancelled"}: raise HTTPException(status_code=409, detail="Closed schemes cannot be edited")
    schedule_map = {s.id: s for s in group.schedules}
    for row in payload.schedules:
        if row.id not in schedule_map: raise HTTPException(status_code=400, detail="Invalid schedule row")
        schedule = schedule_map[row.id]; schedule.due_date = row.due_date; schedule.installment_amount = row.payable_amount; schedule.dividend = 0; schedule.payable_amount = row.payable_amount; schedule.receivable_amount = row.receivable_amount
    await db.commit(); group = await load_group(db, group_id, company.id); return await serialize_group(db, group)


@router.put("/{group_id}/members", response_model=ChitResponse)
async def assign_members(group_id: int, payload: EnrollmentUpdate, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id); group = await load_group(db, group_id, company.id)
    if group.status in {"completed", "cancelled"}: raise HTTPException(status_code=409, detail="Closed schemes cannot accept members")
    if len(set(payload.member_ids)) > group.max_member_count: raise HTTPException(status_code=409, detail=f"Scheme allows a maximum of {group.max_member_count} members")
    valid = set((await db.execute(select(Member.id).where(Member.company_id == company.id, Member.id.in_(payload.member_ids), Member.is_active.is_(True)))).scalars().all())
    if valid != set(payload.member_ids): raise HTTPException(status_code=400, detail="One or more selected members are invalid")
    group.enrollments.clear(); group.enrollments.extend(ChitEnrollment(member_id=member_id, start_installment=1, status="active") for member_id in payload.member_ids); group.status = "active"
    await db.commit(); group = await load_group(db, group_id, company.id); return await serialize_group(db, group)


@router.post("/{group_id}/payments", response_model=ChitDetailResponse, status_code=201)
async def record_payment(group_id: int, payload: PaymentCreate, request: Request, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id); group = await load_group(db, group_id, company.id)
    if group.status != "active": raise HTTPException(status_code=409, detail="Collections are allowed only for active schemes")
    enrollment = next((e for e in group.enrollments if e.member_id == payload.member_id), None)
    if not enrollment or payload.schedule_id not in {s.id for s in group.schedules}: raise HTTPException(status_code=400, detail="Invalid member or installment")
    selected_schedule = next(s for s in group.schedules if s.id == payload.schedule_id)
    if selected_schedule.installment_number < enrollment.start_installment or (enrollment.end_installment is not None and selected_schedule.installment_number > enrollment.end_installment): raise HTTPException(status_code=409, detail="This installment is outside the member's enrollment period")
    auction_settlement = await db.scalar(select(ChitAuction).where(ChitAuction.winner_enrollment_id == enrollment.id, ChitAuction.schedule_id == payload.schedule_id, ChitAuction.status.in_(["pending","approved","paid"])))
    if auction_settlement: raise HTTPException(status_code=409, detail="This installment is settled against the member's auction payout")
    try:
        await validate_branch(db, company.id, payload.branch_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    already_paid = await db.scalar(
        select(func.coalesce(func.sum(ChitPayment.amount), 0)).where(
            ChitPayment.enrollment_id == enrollment.id,
            ChitPayment.schedule_id == payload.schedule_id,
            ChitPayment.status == "posted",
        )
    )
    remaining = selected_schedule.payable_amount - Decimal(already_paid)
    if remaining <= 0: raise HTTPException(status_code=409, detail="This installment is already fully paid")
    if payload.amount > remaining: raise HTTPException(status_code=400, detail=f"Payment exceeds the remaining balance of {remaining}")
    receipt_number = document_number("RCP", company.company_code, payload.payment_date)
    received_amount = payload.received_amount or (payload.amount + payload.late_fee_amount + payload.penalty_amount - payload.waiver_amount + payload.excess_amount)
    expected_received = payload.amount + payload.late_fee_amount + payload.penalty_amount - payload.waiver_amount + payload.excess_amount
    if received_amount != expected_received: raise HTTPException(status_code=400, detail="Received amount does not match principal, charges, waiver, and excess")
    if payload.waiver_amount > 0 and not payload.waiver_reason: raise HTTPException(status_code=400, detail="Waiver reason is required")
    payment = ChitPayment(
        enrollment_id=enrollment.id, schedule_id=payload.schedule_id, amount=payload.amount,
        received_amount=received_amount, late_fee_amount=payload.late_fee_amount, penalty_amount=payload.penalty_amount,
        waiver_amount=payload.waiver_amount, waiver_reason=payload.waiver_reason, excess_amount=payload.excess_amount,
        collection_location_text=payload.collection_location_text, collection_latitude=payload.collection_latitude,
        collection_longitude=payload.collection_longitude,
        payment_date=payload.payment_date, payment_mode=payload.payment_mode,
        reference_number=payload.reference_number, notes=payload.notes,
        receipt_number=receipt_number, branch_id=payload.branch_id,
        collected_by_user_id=user.id, payment_source=payload.payment_source, status="posted",
    )
    db.add(payment); await db.flush()
    cash_account = "cash_on_hand" if payload.payment_mode == "cash" else "bank_clearing"
    try:
        post_entries(
            db, company_id=company.id, branch_id=payload.branch_id, group_id=group.id,
            member_id=enrollment.member_id, source_type="payment", source_id=payment.id,
            entry_date=payload.payment_date, reference_number=receipt_number,
            posted_by_user_id=user.id,
            entries=[
                ("debit", cash_account, received_amount, f"Collection received from {enrollment.member_id}"),
                ("credit", "member_installment_receivable", payload.amount, f"Installment #{selected_schedule.installment_number} collection"),
                *(([("credit", "late_fee_income", payload.late_fee_amount, "Late fee collected")]) if payload.late_fee_amount else []),
                *(([("credit", "penalty_income", payload.penalty_amount, "Penalty collected")]) if payload.penalty_amount else []),
                *(([("credit", "member_advance_liability", payload.excess_amount, "Excess held as member advance")]) if payload.excess_amount else []),
                *(([("debit", "collection_waiver", payload.waiver_amount, "Approved collection waiver")]) if payload.waiver_amount else []),
            ],
        )
    except ValueError as exc:
        await db.rollback(); raise HTTPException(status_code=500, detail=str(exc)) from exc
    add_audit(db, company_id=company.id, user_id=user.id, action="create", entity_type="payment", entity_id=payment.id, description=f"Recorded payment {receipt_number}", request=request, new_values={"amount": str(payload.amount), "member_id": payload.member_id, "schedule_id": payload.schedule_id})
    member=await db.get(Member,enrollment.member_id);add_notification(db,company_id=company.id,user_id=company.owner_id,title=f"Payment collected · {member.full_name}",message=f"₹{received_amount} received for {group.scheme_name} via {payload.payment_mode.upper()} · {receipt_number}",notification_type="payment",href=f"/dashboard/receipts/{payment.id}",entity_type="payment",entity_id=payment.id)
    await db.commit();await notify_payment_collection(db,company=company,member_name=member.full_name,scheme_name=group.scheme_name,amount=received_amount,receipt_number=receipt_number,payment_mode=payload.payment_mode,source=payload.payment_source,entity_id=payment.id,add_in_app=False,member_mobile=member.mobile_number,installment_number=selected_schedule.installment_number,collector_name="Owner/Admin"); group = await load_group(db, group_id, company.id)
    return await serialize_group(db, group, True)


@router.post("/{group_id}/auctions", response_model=ChitDetailResponse, status_code=201)
async def create_auction(group_id: int, payload: AuctionCreate, request: Request, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id); group = await load_group(db, group_id, company.id)
    if group.status != "active": raise HTTPException(status_code=409, detail="Auctions are allowed only for active schemes")
    schedule = next((s for s in group.schedules if s.id == payload.schedule_id), None)
    enrollment = next((e for e in group.enrollments if e.member_id == payload.winner_member_id), None)
    if not schedule or not enrollment: raise HTTPException(status_code=400, detail="Invalid installment or auction winner")
    if schedule.installment_number < enrollment.start_installment or (enrollment.end_installment is not None and schedule.installment_number > enrollment.end_installment): raise HTTPException(status_code=409, detail="This installment is outside the winner's enrollment period")
    if await db.scalar(select(ChitAuction).where(ChitAuction.schedule_id == schedule.id, ChitAuction.status.not_in(["cancelled", "reversed"]))): raise HTTPException(status_code=409, detail="An active auction is already recorded for this installment")
    if await db.scalar(select(ChitAuction.id).join(ChitEnrollment, ChitAuction.winner_enrollment_id == ChitEnrollment.id).where(ChitAuction.group_id == group.id, ChitEnrollment.member_id == enrollment.member_id, ChitAuction.status.not_in(["cancelled", "reversed"]))): raise HTTPException(status_code=409, detail="This member has already won an auction in this scheme")
    if await db.scalar(select(ChitPayment).where(ChitPayment.enrollment_id == enrollment.id, ChitPayment.schedule_id == schedule.id)): raise HTTPException(status_code=409, detail="Winner already has a payment recorded for this installment")
    if schedule.receivable_amount <= 0: raise HTTPException(status_code=400, detail="Enter the schedule receivable amount before settling this auction")
    try:
        await validate_branch(db, company.id, payload.branch_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    settled = schedule.payable_amount
    net_payout = schedule.receivable_amount - settled
    if net_payout < 0: raise HTTPException(status_code=400, detail="Payout must cover the settled installment amount")
    commission = (group.scheme_amount * group.foreman_commission_percent / Decimal("100")).quantize(Decimal("0.01"))
    discount_percent=(payload.discount_amount/group.scheme_amount*Decimal("100")).quantize(Decimal("0.01"))
    if discount_percent<group.minimum_discount_percent or discount_percent>group.maximum_discount_percent: raise HTTPException(status_code=400,detail=f"Discount must be between {group.minimum_discount_percent}% and {group.maximum_discount_percent}%")
    auction = ChitAuction(group_id=group.id, schedule_id=schedule.id, winner_enrollment_id=enrollment.id, auction_date=payload.auction_date, bid_amount=payload.bid_amount, discount_amount=payload.discount_amount, commission_amount=commission, commission_percent=group.foreman_commission_percent, dividend_amount=0, payout_amount=schedule.receivable_amount, settled_installment_amount=settled, net_payout_amount=net_payout, notes=payload.notes, branch_id=payload.branch_id, status="pending")
    db.add(auction); await db.flush()
    db.add(AuctionBid(auction_id=auction.id,bidder_enrollment_id=enrollment.id,bid_amount=payload.bid_amount,discount_amount=payload.discount_amount,sequence_number=1,is_winning_bid=True,recorded_by_user_id=user.id))
    add_audit(db, company_id=company.id, user_id=user.id, action="create", entity_type="auction", entity_id=auction.id, description="Created pending auction", request=request, new_values={"winner_member_id": payload.winner_member_id, "schedule_id": payload.schedule_id, "status": "pending"})
    await db.commit(); group = await load_group(db, group_id, company.id)
    return await serialize_group(db, group, True)


@router.post("/{group_id}/auctions/{auction_id}/bids",status_code=201)
async def add_auction_bid(group_id:int,auction_id:int,payload:AuctionBidCreate,request:Request,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);group=await load_group(db,group_id,company.id);auction=await db.scalar(select(ChitAuction).where(ChitAuction.id==auction_id,ChitAuction.group_id==group.id))
    if not auction or auction.status!="pending": raise HTTPException(status_code=409,detail="Bids can be recorded only for pending auctions")
    enrollment=next((item for item in group.enrollments if item.member_id==payload.bidder_member_id and item.status=="active"),None)
    if not enrollment: raise HTTPException(status_code=400,detail="Bidder is not active in this scheme")
    discount_percent=payload.discount_amount/group.scheme_amount*Decimal("100")
    if discount_percent<group.minimum_discount_percent or discount_percent>group.maximum_discount_percent: raise HTTPException(status_code=400,detail="Bid discount is outside scheme limits")
    sequence=(await db.scalar(select(func.coalesce(func.max(AuctionBid.sequence_number),0)).where(AuctionBid.auction_id==auction.id)))+1;bid=AuctionBid(auction_id=auction.id,bidder_enrollment_id=enrollment.id,bid_amount=payload.bid_amount,discount_amount=payload.discount_amount,sequence_number=sequence,recorded_by_user_id=user.id);db.add(bid);await db.flush();add_audit(db,company_id=company.id,user_id=user.id,action="create",entity_type="auction_bid",entity_id=bid.id,description=f"Recorded bid #{sequence}",request=request,new_values={"member_id":payload.bidder_member_id,"bid_amount":str(payload.bid_amount),"discount_amount":str(payload.discount_amount)});await db.commit();return {"id":bid.id,"sequence_number":sequence,"status":"active"}


@router.get("/{group_id}/auctions/{auction_id}/bids")
async def list_auction_bids(group_id:int,auction_id:int,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);await load_group(db,group_id,company.id);records=(await db.execute(select(AuctionBid,ChitEnrollment,Member).join(ChitEnrollment,AuctionBid.bidder_enrollment_id==ChitEnrollment.id).join(Member,ChitEnrollment.member_id==Member.id).where(AuctionBid.auction_id==auction_id).order_by(AuctionBid.sequence_number))).all();return [{"id":bid.id,"sequence_number":bid.sequence_number,"member_id":member.id,"member_name":member.full_name,"bid_amount":bid.bid_amount,"discount_amount":bid.discount_amount,"is_winning_bid":bid.is_winning_bid,"status":bid.status,"created_at":bid.created_at} for bid,enrollment,member in records]


@router.post("/{group_id}/auctions/{auction_id}/cancel",response_model=ChitDetailResponse)
async def cancel_auction(group_id:int,auction_id:int,payload:CancellationCreate,request:Request,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);group=await load_group(db,group_id,company.id);auction=await db.scalar(select(ChitAuction).where(ChitAuction.id==auction_id,ChitAuction.group_id==group.id))
    if not auction or auction.status not in {"pending","approved"}: raise HTTPException(status_code=409,detail="Only unpaid auctions can be cancelled")
    auction.status="cancelled";auction.cancelled_at=datetime.now(UTC);auction.cancelled_by_user_id=user.id;auction.cancellation_reason=payload.reason;add_audit(db,company_id=company.id,user_id=user.id,action="cancel",entity_type="auction",entity_id=auction.id,description="Cancelled unpaid auction",request=request,new_values={"status":"cancelled","reason":payload.reason});await db.commit();group=await load_group(db,group_id,company.id);return await serialize_group(db,group,True)


@router.post("/{group_id}/cancel",response_model=ChitResponse)
async def cancel_scheme(group_id:int,payload:CancellationCreate,request:Request,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);group=await load_group(db,group_id,company.id)
    if group.status not in {"draft","active"}: raise HTTPException(status_code=409,detail="Only draft or active schemes can be cancelled")
    financial_count=await db.scalar(select(func.count(ChitPayment.id)).join(ChitEnrollment).where(ChitEnrollment.group_id==group.id,ChitPayment.status!="reversed"));auction_count=await db.scalar(select(func.count(ChitAuction.id)).where(ChitAuction.group_id==group.id,ChitAuction.status.in_(["pending","approved","paid"])))
    if financial_count or auction_count: raise HTTPException(status_code=409,detail="Reverse/refund all financial activity and cancel unpaid auctions before cancelling the scheme")
    group.status="cancelled";group.cancelled_at=datetime.now(UTC);group.cancelled_by_user_id=user.id;group.cancellation_reason=payload.reason;add_audit(db,company_id=company.id,user_id=user.id,action="cancel",entity_type="chit_group",entity_id=group.id,description="Cancelled scheme",request=request,new_values={"status":"cancelled","reason":payload.reason});await db.commit();group=await load_group(db,group_id,company.id);return await serialize_group(db,group)


@router.get("/{group_id}/members/{member_id}/ledger", response_model=MemberLedgerResponse)
async def get_member_ledger(group_id: int, member_id: int, user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    company = await require_company(db, user.id); group = await load_group(db, group_id, company.id)
    enrollment = next((e for e in group.enrollments if e.member_id == member_id), None)
    if not enrollment: raise HTTPException(status_code=404, detail="Member is not enrolled in this scheme")
    member = await db.get(Member, member_id)
    payments = (await db.execute(select(ChitPayment).where(ChitPayment.enrollment_id == enrollment.id, ChitPayment.status == "posted"))).scalars().all()
    payments_by_schedule = {}
    for payment in payments:
        payments_by_schedule.setdefault(payment.schedule_id, []).append(payment)
    auctions = (await db.execute(select(ChitAuction).where(ChitAuction.winner_enrollment_id == enrollment.id, ChitAuction.status == "paid"))).scalars().all(); auction_map = {a.schedule_id: a for a in auctions}
    today = date.today(); rows = []
    for schedule in sorted(group.schedules, key=lambda value: value.installment_number):
        if schedule.installment_number < enrollment.start_installment or (enrollment.end_installment is not None and schedule.installment_number > enrollment.end_installment):
            continue
        schedule_payments, auction = payments_by_schedule.get(schedule.id, []), auction_map.get(schedule.id)
        paid_amount = sum((payment.amount for payment in schedule_payments), Decimal("0"))
        balance = max(schedule.payable_amount - paid_amount, Decimal("0"))
        latest_payment = max(schedule_payments, key=lambda value: value.created_at) if schedule_payments else None
        row_status = "settled_against_payout" if auction else "paid" if balance == 0 else "partial" if paid_amount > 0 else "overdue" if schedule.due_date < today else "pending"
        rows.append({"schedule_id": schedule.id, "installment_number": schedule.installment_number, "due_date": schedule.due_date, "payable_amount": schedule.payable_amount, "receivable_amount": schedule.receivable_amount, "status": row_status, "paid_amount": paid_amount if schedule_payments else None, "balance_amount": balance, "payment_date": latest_payment.payment_date if latest_payment else None, "payment_mode": latest_payment.payment_mode if latest_payment else None, "reference_number": latest_payment.reference_number if latest_payment else None, "auction_id": auction.id if auction else None, "payout_amount": auction.payout_amount if auction else None, "net_payout_amount": auction.net_payout_amount if auction else None})
    return {"group_id": group.id, "group_code": group.group_code, "scheme_name": group.scheme_name, "member_id": member.id, "member_code": member.member_code, "member_name": member.full_name, "mobile_number": member.mobile_number, "rows": rows}


async def serialize_transfer(db: AsyncSession, transfer: ChitEnrollmentTransfer):
    old_enrollment = await db.get(ChitEnrollment, transfer.old_enrollment_id)
    old_member = await db.get(Member, old_enrollment.member_id)
    replacement = await db.get(Member, transfer.replacement_member_id)
    return {"id":transfer.id,"group_id":transfer.group_id,"old_enrollment_id":transfer.old_enrollment_id,"old_member_id":old_member.id,"old_member_name":old_member.full_name,"replacement_member_id":replacement.id,"replacement_member_name":replacement.full_name,"new_enrollment_id":transfer.new_enrollment_id,"effective_installment":transfer.effective_installment,"effective_date":transfer.effective_date,"outstanding_balance":transfer.outstanding_balance,"reason":transfer.reason,"status":transfer.status,"old_member_acknowledged_at":transfer.old_member_acknowledged_at,"new_member_acknowledged_at":transfer.new_member_acknowledged_at,"old_member_consent_file_name":transfer.old_member_consent_file_name,"new_member_consent_file_name":transfer.new_member_consent_file_name,"requested_at":transfer.requested_at,"approved_at":transfer.approved_at,"approval_notes":transfer.approval_notes}


@router.post("/{group_id}/enrollments/{enrollment_id}/replace", response_model=EnrollmentTransferResponse, status_code=201)
async def replace_enrollment(
    group_id: int, enrollment_id: int, request: Request,
    replacement_member_id: int = Form(), effective_installment: int = Form(), effective_date: date = Form(),
    reason: str = Form(), old_member_acknowledged: bool = Form(), new_member_acknowledged: bool = Form(),
    old_member_consent: UploadFile = File(), new_member_consent: UploadFile = File(),
    user: User = Depends(require_owner), db: AsyncSession = Depends(get_db),
):
    company = await require_company(db, user.id); group = await load_group(db, group_id, company.id)
    if group.status != "active": raise HTTPException(status_code=409, detail="Replacement is allowed only for active schemes")
    current = next((e for e in group.enrollments if e.id == enrollment_id), None)
    if not current or current.status != "active": raise HTTPException(status_code=409, detail="Only an active enrollment can be replaced")
    if await db.scalar(select(ChitEnrollmentTransfer.id).where(ChitEnrollmentTransfer.old_enrollment_id == current.id, ChitEnrollmentTransfer.status == "pending")): raise HTTPException(status_code=409, detail="A replacement request is already pending for this enrollment")
    if effective_installment <= current.start_installment or effective_installment > group.duration_months: raise HTTPException(status_code=400, detail="Effective installment must be after the member's start and within the scheme duration")
    schedule = next(row for row in group.schedules if row.installment_number == effective_installment)
    if effective_date < schedule.due_date: raise HTTPException(status_code=400, detail="Effective date cannot be before the effective installment date")
    if not old_member_acknowledged or not new_member_acknowledged: raise HTTPException(status_code=400, detail="Both members must acknowledge the transfer")
    if any(e.member_id == replacement_member_id and e.status == "active" for e in group.enrollments): raise HTTPException(status_code=409, detail="Replacement member is already active in this scheme")
    replacement = await db.scalar(select(Member).where(Member.id == replacement_member_id, Member.company_id == company.id, Member.is_active.is_(True)))
    if not replacement: raise HTTPException(status_code=400, detail="Replacement member is invalid")
    paid = await db.scalar(select(func.coalesce(func.sum(ChitPayment.amount - ChitPayment.refunded_amount),0)).where(ChitPayment.enrollment_id==current.id, ChitPayment.status!="reversed"))
    settled = await db.scalar(select(func.coalesce(func.sum(ChitAuction.settled_installment_amount),0)).where(ChitAuction.winner_enrollment_id==current.id, ChitAuction.status=="paid"))
    expected_to_transfer = sum((row.payable_amount for row in group.schedules if row.installment_number < effective_installment and row.installment_number >= current.start_installment),Decimal("0"))
    outstanding = max(expected_to_transfer-Decimal(paid)-Decimal(settled),Decimal("0"))
    now=datetime.now(UTC); transfer=ChitEnrollmentTransfer(group_id=group.id,old_enrollment_id=current.id,replacement_member_id=replacement.id,effective_installment=effective_installment,effective_date=effective_date,outstanding_balance=outstanding,reason=reason,status="pending",requested_by_user_id=user.id,old_member_acknowledged_at=now,new_member_acknowledged_at=now)
    db.add(transfer); await db.flush(); root=Path(settings.upload_directory).resolve()/"private"/"transfers"/company.company_code/str(transfer.id)
    transfer.old_member_consent_path,transfer.old_member_consent_file_name=await save_document(old_member_consent,root/"old-member-consent")
    transfer.new_member_consent_path,transfer.new_member_consent_file_name=await save_document(new_member_consent,root/"new-member-consent")
    add_audit(db,company_id=company.id,user_id=user.id,action="request",entity_type="member_replacement",entity_id=transfer.id,description=f"Requested replacement of enrollment {current.id}",request=request,new_values={"replacement_member_id":replacement.id,"effective_installment":effective_installment,"effective_date":str(effective_date),"outstanding_balance":str(outstanding),"status":"pending"})
    await db.commit(); await db.refresh(transfer); return await serialize_transfer(db,transfer)


@router.get("/{group_id}/transfers", response_model=list[EnrollmentTransferResponse])
async def list_transfers(group_id:int,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id); await load_group(db,group_id,company.id)
    transfers=(await db.execute(select(ChitEnrollmentTransfer).where(ChitEnrollmentTransfer.group_id==group_id).order_by(ChitEnrollmentTransfer.requested_at.desc()))).scalars().all()
    return [await serialize_transfer(db,item) for item in transfers]


@router.post("/{group_id}/transfers/{transfer_id}/approve", response_model=ChitDetailResponse)
async def approve_transfer(group_id:int,transfer_id:int,payload:EnrollmentTransferApproval,request:Request,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id); group=await load_group(db,group_id,company.id)
    transfer=await db.scalar(select(ChitEnrollmentTransfer).where(ChitEnrollmentTransfer.id==transfer_id,ChitEnrollmentTransfer.group_id==group.id))
    if not transfer: raise HTTPException(status_code=404,detail="Replacement request not found")
    if transfer.status!="pending": raise HTTPException(status_code=409,detail="Only pending replacement requests can be approved")
    current=next((item for item in group.enrollments if item.id==transfer.old_enrollment_id),None)
    if not current or current.status!="active": raise HTTPException(status_code=409,detail="Original enrollment is no longer active")
    if transfer.outstanding_balance>0: raise HTTPException(status_code=409,detail=f"Clear the outstanding transfer balance of {transfer.outstanding_balance} before approval")
    new_enrollment=ChitEnrollment(group_id=group.id,member_id=transfer.replacement_member_id,start_installment=transfer.effective_installment,status="active")
    db.add(new_enrollment);await db.flush();current.end_installment=transfer.effective_installment-1;current.status="discontinued";current.break_reason=transfer.reason;current.replaced_enrollment_id=new_enrollment.id
    transfer.new_enrollment_id=new_enrollment.id;transfer.status="approved";transfer.approved_by_user_id=user.id;transfer.approved_at=datetime.now(UTC);transfer.approval_notes=payload.approval_notes
    add_audit(db,company_id=company.id,user_id=user.id,action="approve",entity_type="member_replacement",entity_id=transfer.id,description=f"Approved replacement of enrollment {current.id}",request=request,old_values={"status":"pending"},new_values={"status":"approved","new_enrollment_id":new_enrollment.id})
    await db.commit();group=await load_group(db,group_id,company.id);return await serialize_group(db,group,True)


@router.get("/{group_id}/transfers/{transfer_id}/documents/{party}")
async def transfer_consent_document(group_id:int,transfer_id:int,party:str,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);await load_group(db,group_id,company.id)
    transfer=await db.scalar(select(ChitEnrollmentTransfer).where(ChitEnrollmentTransfer.id==transfer_id,ChitEnrollmentTransfer.group_id==group_id))
    if not transfer or party not in {"old-member","new-member"}: raise HTTPException(status_code=404,detail="Consent document not found")
    path=transfer.old_member_consent_path if party=="old-member" else transfer.new_member_consent_path;name=transfer.old_member_consent_file_name if party=="old-member" else transfer.new_member_consent_file_name
    if not path or not Path(path).is_file(): raise HTTPException(status_code=404,detail="Consent document not found")
    return FileResponse(path,filename=name,content_disposition_type="inline")


