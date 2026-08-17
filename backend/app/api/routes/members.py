import hashlib
import secrets
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import require_owner
from app.api.routes.companies import get_owner_company
from app.core.config import settings
from app.db.session import get_db
from app.models.member import Member, MemberReference
from app.models.advance import AdvancePayment
from app.models.chit import ChitAuction, ChitEnrollment, ChitGroup, ChitPayment, LedgerEntry, PaymentRefund
from app.models.user import User
from app.schemas.member import MemberArchive, MemberCreate, MemberFinancialSummary, MemberKycReview, MemberListResponse, MemberResponse, MemberUpdate
from app.services.audit import add_audit

router = APIRouter(prefix="/api/v1/members", tags=["Members"])
ALLOWED_DOCUMENT_TYPES = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}
DOCUMENT_FIELDS = {
    "photo": ("photo_path", "photo_file_name"),
    "aadhaar": ("aadhaar_document_path", "aadhaar_document_file_name"),
    "pan": ("pan_document_path", "pan_document_file_name"),
    "cheque": ("cheque_path", "cheque_file_name"),
    "bank-statement": ("bank_statement_path", "bank_statement_file_name"),
}


def generate_member_code() -> str:
    return f"MEM-{secrets.token_hex(4).upper()}"


def aadhaar_digest(number: str) -> str:
    return hashlib.sha256(number.encode()).hexdigest()


async def require_company(db: AsyncSession, owner_id: int):
    company = await get_owner_company(db, owner_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Complete company onboarding first")
    return company


@router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def create_member(payload: MemberCreate, request: Request, current_user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)) -> Member:
    company = await require_company(db, current_user.id)
    member = Member(
        company_id=company.id, member_code=generate_member_code(),
        full_name=payload.full_name.strip(), date_of_birth=payload.date_of_birth, gender=payload.gender, mobile_number=payload.mobile_number,
        email=str(payload.email).lower() if payload.email else None,
        aadhaar_hash=aadhaar_digest(payload.aadhaar_number), aadhaar_last4=payload.aadhaar_number[-4:],
        pan=payload.pan, nominee_name=payload.nominee_name, nominee_relationship=payload.nominee_relationship,
        nominee_mobile_number=payload.nominee_mobile_number, nominee_date_of_birth=payload.nominee_date_of_birth,
        bank_account_holder_name=payload.bank_account_holder_name, bank_account_number=payload.bank_account_number,
        bank_name=payload.bank_name, bank_branch_name=payload.bank_branch_name,
        bank_ifsc_code=payload.bank_ifsc_code, bank_account_type=payload.bank_account_type,
        internal_notes=payload.internal_notes, risk_flags=payload.risk_flags,
        address_line_1=payload.address_line_1.strip(),
        address_line_2=payload.address_line_2, locality=payload.locality,
        city=payload.city.strip(), state=payload.state.strip(), postal_code=payload.postal_code,
        country=payload.country, landmark=payload.landmark,
    )
    member.references = [MemberReference(**reference.model_dump()) for reference in payload.references]
    db.add(member)
    try:
        await db.flush(); add_audit(db,company_id=company.id,user_id=current_user.id,action="create",entity_type="member",entity_id=member.id,description=f"Created member {member.member_code}",request=request,new_values={"full_name":member.full_name,"kyc_status":"pending"}); await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A member with this mobile number or Aadhaar already exists") from exc
    result = await db.execute(select(Member).where(Member.id == member.id).options(selectinload(Member.references)))
    return result.scalar_one()


@router.get("", response_model=MemberListResponse)
async def list_members(
    search: str | None = Query(default=None, max_length=100), include_archived: bool = False, page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100), current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> MemberListResponse:
    company = await require_company(db, current_user.id)
    filters = [Member.company_id == company.id]
    if not include_archived: filters.append(Member.is_active.is_(True))
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(Member.full_name.ilike(term), Member.mobile_number.ilike(term), Member.member_code.ilike(term)))
    total = await db.scalar(select(func.count(Member.id)).where(*filters)) or 0
    result = await db.execute(
        select(Member).where(*filters).options(selectinload(Member.references))
        .order_by(Member.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return MemberListResponse(items=list(result.scalars().all()), total=total, page=page, page_size=page_size)


@router.get("/{member_id}", response_model=MemberResponse)
async def get_member(member_id: int, current_user: User = Depends(require_owner), db: AsyncSession = Depends(get_db)) -> Member:
    company = await require_company(db, current_user.id)
    result = await db.execute(select(Member).where(Member.id == member_id, Member.company_id == company.id).options(selectinload(Member.references)))
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    return member


@router.get("/{member_id}/financial-summary", response_model=MemberFinancialSummary)
async def get_member_financial_summary(
    member_id: int, current_user: User = Depends(require_owner), db: AsyncSession = Depends(get_db),
) -> MemberFinancialSummary:
    company = await require_company(db, current_user.id)
    member = await db.scalar(select(Member).where(Member.id == member_id, Member.company_id == company.id))
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    payment_result = await db.execute(
        select(func.coalesce(func.sum(ChitPayment.amount), 0), func.count(ChitPayment.id))
        .join(ChitEnrollment, ChitPayment.enrollment_id == ChitEnrollment.id)
        .join(ChitGroup, ChitEnrollment.group_id == ChitGroup.id)
        .where(ChitEnrollment.member_id == member.id, ChitGroup.company_id == company.id)
    )
    total_collected, payment_count = payment_result.one()
    auction_result = await db.execute(
        select(
            func.count(ChitAuction.id),
            func.coalesce(func.sum(ChitAuction.payout_amount), 0),
            func.coalesce(func.sum(ChitAuction.net_payout_amount), 0),
        )
        .join(ChitEnrollment, ChitAuction.winner_enrollment_id == ChitEnrollment.id)
        .join(ChitGroup, ChitAuction.group_id == ChitGroup.id)
        .where(ChitEnrollment.member_id == member.id, ChitGroup.company_id == company.id)
    )
    settlement_count, gross_payout, net_payout = auction_result.one()
    return MemberFinancialSummary(
        total_collected=total_collected,
        payment_count=payment_count,
        auction_settlement_count=settlement_count,
        gross_payout=gross_payout,
        net_payout=net_payout,
    )


@router.put("/{member_id}", response_model=MemberResponse)
async def update_member(
    member_id: int, payload: MemberUpdate, request: Request, current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> Member:
    company = await require_company(db, current_user.id)
    result = await db.execute(
        select(Member).where(Member.id == member_id, Member.company_id == company.id)
        .options(selectinload(Member.references))
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    member.full_name = payload.full_name.strip()
    member.date_of_birth = payload.date_of_birth
    member.gender = payload.gender
    member.mobile_number = payload.mobile_number
    member.email = str(payload.email).lower() if payload.email else None
    if payload.aadhaar_number:
        member.aadhaar_hash = aadhaar_digest(payload.aadhaar_number)
        member.aadhaar_last4 = payload.aadhaar_number[-4:]
    member.pan = payload.pan
    member.nominee_name = payload.nominee_name
    member.nominee_relationship = payload.nominee_relationship
    member.nominee_mobile_number = payload.nominee_mobile_number
    member.nominee_date_of_birth = payload.nominee_date_of_birth
    member.bank_account_holder_name = payload.bank_account_holder_name
    member.bank_account_number = payload.bank_account_number
    member.bank_name = payload.bank_name
    member.bank_branch_name = payload.bank_branch_name
    member.bank_ifsc_code = payload.bank_ifsc_code
    member.bank_account_type = payload.bank_account_type
    member.internal_notes = payload.internal_notes
    member.risk_flags = payload.risk_flags
    member.address_line_1 = payload.address_line_1.strip()
    member.address_line_2 = payload.address_line_2
    member.locality = payload.locality
    member.city = payload.city.strip()
    member.state = payload.state.strip()
    member.postal_code = payload.postal_code
    member.country = payload.country
    member.landmark = payload.landmark
    member.references.clear()
    member.references.extend(MemberReference(**reference.model_dump()) for reference in payload.references)
    try:
        add_audit(db,company_id=company.id,user_id=current_user.id,action="update",entity_type="member",entity_id=member.id,description=f"Updated member {member.member_code}",request=request,new_values={"full_name":member.full_name,"risk_flags":member.risk_flags}); await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A member with this mobile number or Aadhaar already exists") from exc
    refreshed = await db.execute(
        select(Member).where(Member.id == member.id).options(selectinload(Member.references))
    )
    return refreshed.scalar_one()


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(
    member_id: int, request: Request, reason: str = Query(default="Archived by owner",min_length=3,max_length=500), current_user: User = Depends(require_owner), db: AsyncSession = Depends(get_db),
) -> None:
    company = await require_company(db, current_user.id)
    member = await db.scalar(select(Member).where(Member.id == member_id, Member.company_id == company.id))
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if not member.is_active: raise HTTPException(status_code=409,detail="Member is already archived")
    member.is_active=False;member.archived_at=datetime.now(UTC);member.archived_by_user_id=current_user.id;member.archive_reason=reason
    add_audit(db,company_id=company.id,user_id=current_user.id,action="archive",entity_type="member",entity_id=member.id,description=f"Archived member {member.member_code}",request=request,old_values={"is_active":True},new_values={"is_active":False,"reason":reason});await db.commit()


@router.post("/{member_id}/restore",response_model=MemberResponse)
async def restore_member(member_id:int,request:Request,current_user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,current_user.id);member=await db.scalar(select(Member).where(Member.id==member_id,Member.company_id==company.id).options(selectinload(Member.references)))
    if not member: raise HTTPException(status_code=404,detail="Member not found")
    member.is_active=True;member.archived_at=None;member.archived_by_user_id=None;member.archive_reason=None
    add_audit(db,company_id=company.id,user_id=current_user.id,action="restore",entity_type="member",entity_id=member.id,description=f"Restored member {member.member_code}",request=request,new_values={"is_active":True});await db.commit();await db.refresh(member);return member


@router.put("/{member_id}/kyc",response_model=MemberResponse)
async def review_member_kyc(member_id:int,payload:MemberKycReview,request:Request,current_user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,current_user.id);member=await db.scalar(select(Member).where(Member.id==member_id,Member.company_id==company.id).options(selectinload(Member.references)))
    if not member: raise HTTPException(status_code=404,detail="Member not found")
    if payload.aadhaar_status=="verified" and not member.aadhaar_document_path: raise HTTPException(status_code=409,detail="Upload Aadhaar evidence before verification")
    if payload.pan_status=="verified" and not member.pan_document_path: raise HTTPException(status_code=409,detail="Upload PAN evidence before verification")
    rejected=payload.aadhaar_status=="rejected" or payload.pan_status=="rejected"
    if rejected and not payload.rejection_reason: raise HTTPException(status_code=400,detail="Rejection reason is required")
    now=datetime.now(UTC);old={"kyc_status":member.kyc_status,"aadhaar_status":member.aadhaar_verification_status,"pan_status":member.pan_verification_status}
    member.aadhaar_verification_status=payload.aadhaar_status;member.pan_verification_status=payload.pan_status;member.aadhaar_verified_at=now if payload.aadhaar_status=="verified" else None;member.pan_verified_at=now if payload.pan_status=="verified" else None;member.kyc_status="rejected" if rejected else "verified";member.kyc_reviewed_at=now;member.kyc_reviewed_by_user_id=current_user.id;member.kyc_rejection_reason=payload.rejection_reason;member.kyc_notes=payload.notes
    add_audit(db,company_id=company.id,user_id=current_user.id,action="review",entity_type="member_kyc",entity_id=member.id,description=f"Reviewed KYC for {member.member_code}",request=request,old_values=old,new_values={"kyc_status":member.kyc_status,"aadhaar_status":payload.aadhaar_status,"pan_status":payload.pan_status,"rejection_reason":payload.rejection_reason});await db.commit();await db.refresh(member);return member


@router.get("/{member_id}/ledger")
async def consolidated_member_ledger(member_id:int,current_user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,current_user.id);member=await db.scalar(select(Member).where(Member.id==member_id,Member.company_id==company.id))
    if not member: raise HTTPException(status_code=404,detail="Member not found")
    enrollments=(await db.execute(select(ChitEnrollment,ChitGroup).join(ChitGroup,ChitEnrollment.group_id==ChitGroup.id).where(ChitEnrollment.member_id==member.id,ChitGroup.company_id==company.id))).all();enrollment_ids=[item.id for item,_ in enrollments]
    payments=list((await db.execute(select(ChitPayment).where(ChitPayment.enrollment_id.in_(enrollment_ids)).order_by(ChitPayment.created_at.desc()))).scalars().all()) if enrollment_ids else []
    auctions=list((await db.execute(select(ChitAuction).where(ChitAuction.winner_enrollment_id.in_(enrollment_ids)).order_by(ChitAuction.created_at.desc()))).scalars().all()) if enrollment_ids else []
    advances=list((await db.execute(select(AdvancePayment).join(ChitEnrollment,AdvancePayment.enrollment_id==ChitEnrollment.id).where(ChitEnrollment.member_id==member.id,AdvancePayment.company_id==company.id).order_by(AdvancePayment.created_at.desc()))).scalars().all())
    entries=list((await db.execute(select(LedgerEntry).where(LedgerEntry.company_id==company.id,LedgerEntry.member_id==member.id).order_by(LedgerEntry.entry_date.desc(),LedgerEntry.id.desc()))).scalars().all())
    return {"schemes":[{"group_id":group.id,"group_code":group.group_code,"scheme_name":group.scheme_name,"enrollment_id":enrollment.id,"start_installment":enrollment.start_installment,"end_installment":enrollment.end_installment,"status":enrollment.status} for enrollment,group in enrollments],"payments":[{"id":p.id,"receipt_number":p.receipt_number,"amount":p.amount,"received_amount":p.received_amount,"refunded_amount":p.refunded_amount,"payment_date":p.payment_date,"status":p.status} for p in payments],"auctions":[{"id":a.id,"voucher_number":a.voucher_number,"payout_amount":a.payout_amount,"net_payout_amount":a.net_payout_amount,"auction_date":a.auction_date,"status":a.status} for a in auctions],"advances":[{"id":a.id,"receipt_number":a.receipt_number,"amount":a.amount,"allocated_amount":a.allocated_amount,"payment_date":a.payment_date,"status":a.status} for a in advances],"ledger_entries":[{"id":e.id,"entry_date":e.entry_date,"entry_type":e.entry_type,"account_code":e.account_code,"amount":e.amount,"description":e.description,"reference_number":e.reference_number,"is_reversal":e.is_reversal} for e in entries]}


@router.get("/{member_id}/documents/{document_type}")
async def get_member_document(
    member_id: int, document_type: str, current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    company = await require_company(db, current_user.id)
    fields = DOCUMENT_FIELDS.get(document_type)
    if fields is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document type not found")
    member = await db.scalar(select(Member).where(Member.id == member_id, Member.company_id == company.id))
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    path_value = getattr(member, fields[0])
    file_name = getattr(member, fields[1])
    if not path_value or not Path(path_value).is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return FileResponse(path_value, filename=file_name, content_disposition_type="inline")


async def save_document(file: UploadFile, destination: Path) -> tuple[str, str]:
    if file.content_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Document must be PDF, JPEG, or PNG")
    max_size = 10 * 1024 * 1024
    content = await file.read(max_size + 1)
    await file.close()
    if len(content) > max_size:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Document must not exceed 10 MB")
    valid_signature = (
        (file.content_type == "application/pdf" and content.startswith(b"%PDF-"))
        or (file.content_type == "image/jpeg" and content.startswith(b"\xff\xd8\xff"))
        or (file.content_type == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n"))
    )
    if not valid_signature:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Document content does not match its declared file type")
    extension = ALLOWED_DOCUMENT_TYPES[file.content_type]
    path = destination.with_suffix(extension)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return str(path), (file.filename or path.name)[:255]


@router.post("/{member_id}/documents", response_model=MemberResponse)
async def upload_member_documents(
    member_id: int, photo: UploadFile | None = File(default=None),
    aadhaar_document: UploadFile | None = File(default=None), pan_document: UploadFile | None = File(default=None),
    cheque: UploadFile | None = File(default=None),
    bank_statement: UploadFile | None = File(default=None), current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> Member:
    company = await require_company(db, current_user.id)
    result = await db.execute(select(Member).where(Member.id == member_id, Member.company_id == company.id).options(selectinload(Member.references)))
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    root = Path(settings.upload_directory).resolve() / "private" / "members" / company.company_code / member.member_code
    if photo:
        if photo.content_type not in {"image/jpeg", "image/png"}:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Member photo must be JPEG or PNG")
        member.photo_path, member.photo_file_name = await save_document(photo, root / "photo")
    if aadhaar_document:
        member.aadhaar_document_path, member.aadhaar_document_file_name = await save_document(
            aadhaar_document, root / "aadhaar"
        )
    if pan_document:
        member.pan_document_path, member.pan_document_file_name = await save_document(
            pan_document, root / "pan"
        )
    if cheque:
        member.cheque_path, member.cheque_file_name = await save_document(cheque, root / "cheque")
    if bank_statement:
        member.bank_statement_path, member.bank_statement_file_name = await save_document(bank_statement, root / "bank-statement")
    await db.commit()
    refreshed = await db.execute(
        select(Member)
        .where(Member.id == member.id, Member.company_id == company.id)
        .options(selectinload(Member.references))
    )
    return refreshed.scalar_one()
