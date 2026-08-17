from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("company_id", "employee_code", name="uq_employee_company_code"),
        UniqueConstraint("company_id", "mobile_number", name="uq_employee_company_mobile"),
        UniqueConstraint("company_id", "aadhaar_hash", name="uq_employee_company_aadhaar"),
        UniqueConstraint("company_id", "pan", name="uq_employee_company_pan"),
        UniqueConstraint("company_id", "uan", name="uq_employee_company_uan"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True)
    employee_code: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    father_or_spouse_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(30), nullable=True)
    marital_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String(10), nullable=True)
    mobile_number: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    alternate_mobile_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    personal_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    official_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    current_address: Mapped[str] = mapped_column(String(1000), nullable=False)
    permanent_address: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    department: Mapped[str] = mapped_column(String(120), nullable=False)
    designation: Mapped[str] = mapped_column(String(120), nullable=False)
    employment_type: Mapped[str] = mapped_column(String(30), nullable=False)
    work_mode: Mapped[str] = mapped_column(String(20), default="office", nullable=False)
    joining_date: Mapped[date] = mapped_column(Date, nullable=False)
    probation_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reporting_manager_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    collection_agent_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    emergency_contact_name: Mapped[str] = mapped_column(String(200), nullable=False)
    emergency_contact_relationship: Mapped[str] = mapped_column(String(80), nullable=False)
    emergency_contact_mobile: Mapped[str] = mapped_column(String(20), nullable=False)
    emergency_contact_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    nominee_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    nominee_relationship: Mapped[str | None] = mapped_column(String(80), nullable=True)
    nominee_date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    nominee_mobile_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nominee_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    nominee_share_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=100, nullable=False)
    bank_account_holder_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bank_account_number: Mapped[str | None] = mapped_column(String(34), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    bank_branch_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    bank_ifsc_code: Mapped[str | None] = mapped_column(String(11), nullable=True)
    bank_account_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    aadhaar_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    aadhaar_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(10), nullable=True)
    uan: Mapped[str | None] = mapped_column(String(12), nullable=True)
    pf_member_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    esic_ip_number: Mapped[str | None] = mapped_column(String(10), nullable=True)
    professional_tax_applicable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    labour_welfare_fund_applicable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tax_regime: Mapped[str] = mapped_column(String(10), default="new", nullable=False)
    kyc_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    aadhaar_verification_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    pan_verification_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    bank_verification_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    kyc_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    kyc_reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    kyc_rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    kyc_notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    archive_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    salary_structures: Mapped[list["EmployeeSalaryStructure"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    documents: Mapped[list["EmployeeDocument"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class EmployeeSalaryStructure(Base):
    __tablename__ = "employee_salary_structures"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    annual_ctc: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    basic: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    hra: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    allowances: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    incentives: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    employee_pf: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    employee_esi: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    professional_tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    tds: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    other_deductions: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    gross_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    net_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EmployeeDocument(Base):
    __tablename__ = "employee_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True, nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=False)
    verification_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
