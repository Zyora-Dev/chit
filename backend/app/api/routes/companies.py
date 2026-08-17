import secrets
import logging
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import require_owner
from app.core.config import settings
from app.db.session import get_db
from app.models.company import Company, CompanyAddress
from app.models.user import User
from app.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate, LogoResponse
from app.services.audit import add_audit
from app.services.communications import get_platform_whatsapp_settings, send_whatsapp_template

router = APIRouter(prefix="/api/v1/companies", tags=["Company Onboarding"])
logger = logging.getLogger(__name__)

ALLOWED_LOGO_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def has_valid_image_signature(content: bytes, content_type: str) -> bool:
    if content_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")
    if content_type == "image/webp":
        return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    return False


def generate_company_code() -> str:
    return f"ZCH-{secrets.token_hex(5).upper()}"


async def get_owner_company(db: AsyncSession, owner_id: int) -> Company | None:
    result = await db.execute(
        select(Company)
        .where(Company.owner_id == owner_id)
        .options(selectinload(Company.addresses))
    )
    return result.scalar_one_or_none()


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def onboard_company(
    payload: CompanyCreate,
    current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> Company:
    if await get_owner_company(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company onboarding is already completed for this owner",
        )

    company = Company(
        company_code=generate_company_code(),
        owner_id=current_user.id,
        name=payload.name.strip(),
        legal_name=payload.legal_name.strip() if payload.legal_name else None,
        mobile_number=payload.mobile_number,
        email=str(payload.email).lower(),
        gstin=payload.gstin,
        pan=payload.pan,
        website=str(payload.website) if payload.website else None,
    )
    company.addresses = [
        CompanyAddress(**address.model_dump()) for address in payload.addresses
    ]
    db.add(company)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company code, owner, or GSTIN already exists",
        ) from exc

    company = await get_owner_company(db, current_user.id)
    if company and not company.welcome_whatsapp_sent_at:
        company_id = company.id
        try:
            whatsapp_config = await get_platform_whatsapp_settings(db)
            if whatsapp_config:
                result = await send_whatsapp_template(whatsapp_config, recipient=company.mobile_number, template_name="welcome", language_code="en")
                company.welcome_whatsapp_sent_at = datetime.now(UTC)
                message_id = (result.get("messages") or [{}])[0].get("id")
                add_audit(db, company_id=company.id, user_id=current_user.id, action="whatsapp.welcome", entity_type="company", entity_id=company.id, description="Sent default WhatsApp welcome after company onboarding", new_values={"recipient":company.mobile_number[-4:].rjust(len(company.mobile_number),"*"),"template_name":"welcome","language_code":"en","message_id":message_id})
                await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("Unable to send onboarding WhatsApp welcome", extra={"company_id": company_id})

    return await get_owner_company(db, current_user.id)  # type: ignore[return-value]


@router.get("/me", response_model=CompanyResponse)
async def get_my_company(
    current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> Company:
    company = await get_owner_company(db, current_user.id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.put("/me", response_model=CompanyResponse)
async def update_my_company(
    payload: CompanyUpdate,
    current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> Company:
    company = await get_owner_company(db, current_user.id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    company.name = payload.name.strip()
    company.legal_name = payload.legal_name.strip() if payload.legal_name else None
    company.mobile_number = payload.mobile_number
    company.email = str(payload.email).lower()
    company.gstin = payload.gstin
    company.pan = payload.pan
    company.website = str(payload.website) if payload.website else None
    existing_addresses = list(company.addresses)
    for index, address_payload in enumerate(payload.addresses):
        values = address_payload.model_dump()
        if index < len(existing_addresses):
            for field, value in values.items():
                setattr(existing_addresses[index], field, value)
        else:
            company.addresses.append(CompanyAddress(**values))
    for obsolete_address in existing_addresses[len(payload.addresses):]:
        company.addresses.remove(obsolete_address)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="GSTIN is already registered") from exc
    return await get_owner_company(db, current_user.id)  # type: ignore[return-value]


@router.post("/me/logo", response_model=LogoResponse)
async def upload_company_logo(
    logo: UploadFile = File(...),
    current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> LogoResponse:
    company = await get_owner_company(db, current_user.id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complete company onboarding before uploading a logo",
        )
    if logo.content_type not in ALLOWED_LOGO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Logo must be a PNG, JPEG, or WebP image",
        )

    max_size = settings.max_logo_size_mb * 1024 * 1024
    content = await logo.read(max_size + 1)
    await logo.close()
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Logo must not exceed {settings.max_logo_size_mb} MB",
        )
    if not has_valid_image_signature(content, logo.content_type):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Logo content does not match its declared image type",
        )

    extension = ALLOWED_LOGO_TYPES[logo.content_type]
    relative_path = Path("companies") / company.company_code / f"logo{extension}"
    upload_root = Path(settings.upload_directory).resolve()
    destination = upload_root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)

    for old_logo in destination.parent.glob("logo.*"):
        if old_logo != destination and old_logo.is_file():
            old_logo.unlink()
    destination.write_bytes(content)

    company.logo_url = f"/uploads/{relative_path.as_posix()}"
    await db.commit()
    return LogoResponse(logo_url=company.logo_url)
