from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, JSON, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from app.db.base import Base


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (
        UniqueConstraint("company_id", "mobile_number", name="uq_members_company_mobile"),
        UniqueConstraint("company_id", "aadhaar_hash", name="uq_members_company_aadhaar"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    member_code: Mapped[str] = mapped_column(String(24), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(30), nullable=True)
    mobile_number: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    aadhaar_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    aadhaar_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    pan: Mapped[str | None] = mapped_column(String(10), nullable=True)
    nominee_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    nominee_relationship: Mapped[str | None] = mapped_column(String(80), nullable=True)
    nominee_mobile_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nominee_date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    bank_account_holder_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bank_account_number: Mapped[str | None] = mapped_column(String(34), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    bank_branch_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    bank_ifsc_code: Mapped[str | None] = mapped_column(String(11), nullable=True)
    bank_account_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    kyc_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    aadhaar_verification_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    pan_verification_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    aadhaar_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pan_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    kyc_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    kyc_reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    kyc_rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    kyc_notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    risk_flags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    archive_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    address_line_1: Mapped[str] = mapped_column(String(250), nullable=False)
    address_line_2: Mapped[str | None] = mapped_column(String(250), nullable=True)
    locality: Mapped[str | None] = mapped_column(String(150), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(12), nullable=False)
    country: Mapped[str] = mapped_column(String(100), default="India", server_default="India", nullable=False)
    landmark: Mapped[str | None] = mapped_column(String(200), nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    photo_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    aadhaar_document_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    aadhaar_document_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pan_document_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pan_document_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cheque_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cheque_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bank_statement_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bank_statement_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    references: Mapped[list["MemberReference"]] = orm_relationship(
        back_populates="member", cascade="all, delete-orphan", lazy="selectin"
    )


class MemberReference(Base):
    __tablename__ = "member_references"

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    mobile_number: Mapped[str] = mapped_column(String(20), nullable=False)
    relationship: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    member: Mapped[Member] = orm_relationship(back_populates="references")
