from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator


class MemberReferenceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    mobile_number: str = Field(pattern=r"^\+?[1-9]\d{7,14}$")
    relationship: str | None = Field(default=None, max_length=80)


class MemberCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, pattern=r"^(male|female|other|prefer_not_to_say)$")
    mobile_number: str = Field(pattern=r"^\+?[1-9]\d{7,14}$")
    email: EmailStr | None = None
    aadhaar_number: str
    pan: str | None = None
    nominee_name: str | None = Field(default=None, max_length=200)
    nominee_relationship: str | None = Field(default=None, max_length=80)
    nominee_mobile_number: str | None = Field(default=None, pattern=r"^\+?[1-9]\d{7,14}$")
    nominee_date_of_birth: date | None = None
    bank_account_holder_name: str | None = Field(default=None, max_length=200)
    bank_account_number: str | None = Field(default=None, min_length=6, max_length=34, pattern=r"^[A-Za-z0-9]+$")
    bank_name: str | None = Field(default=None, max_length=150)
    bank_branch_name: str | None = Field(default=None, max_length=150)
    bank_ifsc_code: str | None = Field(default=None, pattern=r"^[A-Za-z]{4}0[A-Za-z0-9]{6}$")
    bank_account_type: str | None = Field(default=None, pattern=r"^(savings|current|other)$")
    internal_notes: str | None = Field(default=None, max_length=1000)
    risk_flags: list[str] = Field(default_factory=list, max_length=20)
    address_line_1: str = Field(min_length=3, max_length=250)
    address_line_2: str | None = Field(default=None, max_length=250)
    locality: str | None = Field(default=None, max_length=150)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    postal_code: str = Field(pattern=r"^[A-Za-z0-9 -]{3,12}$")
    country: str = Field(default="India", min_length=2, max_length=100)
    landmark: str | None = Field(default=None, max_length=200)
    references: list[MemberReferenceCreate] = Field(default_factory=list, max_length=10)

    @field_validator("aadhaar_number")
    @classmethod
    def validate_aadhaar(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = "".join(character for character in value if character.isdigit())
        if len(normalized) != 12:
            raise ValueError("Aadhaar number must contain 12 digits")
        return normalized

    @field_validator("pan", "bank_ifsc_code")
    @classmethod
    def uppercase_codes(cls, value: str | None) -> str | None:
        return value.strip().upper() if value and value.strip() else None


class MemberUpdate(MemberCreate):
    aadhaar_number: str | None = None

    @field_validator("aadhaar_number")
    @classmethod
    def validate_optional_aadhaar(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = "".join(character for character in value if character.isdigit())
        if len(normalized) != 12:
            raise ValueError("Aadhaar number must contain 12 digits")
        return normalized

    @field_validator("pan")
    @classmethod
    def validate_pan(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().upper()
        if len(normalized) != 10 or not normalized.isalnum():
            raise ValueError("PAN must contain 10 alphanumeric characters")
        return normalized


class MemberReferenceResponse(BaseModel):
    id: int
    name: str
    mobile_number: str
    relationship: str | None
    model_config = {"from_attributes": True}


class MemberResponse(BaseModel):
    id: int
    member_code: str
    full_name: str
    date_of_birth: date | None
    gender: str | None
    mobile_number: str
    email: EmailStr | None
    aadhaar_last4: str
    pan: str | None
    nominee_name: str | None
    nominee_relationship: str | None
    nominee_mobile_number: str | None
    nominee_date_of_birth: date | None
    bank_account_holder_name: str | None
    bank_account_number: str | None
    bank_name: str | None
    bank_branch_name: str | None
    bank_ifsc_code: str | None
    bank_account_type: str | None
    kyc_status: str; aadhaar_verification_status: str; pan_verification_status: str
    aadhaar_verified_at: datetime | None; pan_verified_at: datetime | None
    kyc_reviewed_at: datetime | None; kyc_reviewed_by_user_id: int | None
    kyc_rejection_reason: str | None; kyc_notes: str | None
    internal_notes: str | None; risk_flags: list[str]
    archived_at: datetime | None; archived_by_user_id: int | None; archive_reason: str | None
    address_line_1: str
    address_line_2: str | None
    locality: str | None
    city: str
    state: str
    postal_code: str
    country: str
    landmark: str | None
    photo_file_name: str | None
    aadhaar_document_file_name: str | None
    pan_document_file_name: str | None
    cheque_file_name: str | None
    bank_statement_file_name: str | None
    is_active: bool
    references: list[MemberReferenceResponse]
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class MemberListResponse(BaseModel):
    items: list[MemberResponse]
    total: int
    page: int
    page_size: int


class MemberFinancialSummary(BaseModel):
    total_collected: Decimal
    payment_count: int
    auction_settlement_count: int
    gross_payout: Decimal
    net_payout: Decimal


class MemberKycReview(BaseModel):
    aadhaar_status: str = Field(pattern=r"^(verified|rejected)$")
    pan_status: str = Field(pattern=r"^(verified|rejected|not_applicable)$")
    notes: str | None = Field(default=None, max_length=1000)
    rejection_reason: str | None = Field(default=None, max_length=500)


class MemberArchive(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
