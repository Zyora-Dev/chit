from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChitGroup(Base):
    __tablename__ = "chit_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    group_code: Mapped[str] = mapped_column(String(24), unique=True, index=True, nullable=False)
    scheme_name: Mapped[str] = mapped_column(String(200), nullable=False)
    scheme_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_months: Mapped[int] = mapped_column(Integer, nullable=False)
    max_member_count: Mapped[int] = mapped_column(Integer, nullable=False)
    foreman_commission_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    grace_period_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    late_fee_type: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    late_fee_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    auction_weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    auction_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    minimum_discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    maximum_discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=100, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    schedules: Mapped[list["ChitSchedule"]] = relationship(back_populates="group", cascade="all, delete-orphan", lazy="selectin")
    enrollments: Mapped[list["ChitEnrollment"]] = relationship(back_populates="group", cascade="all, delete-orphan", lazy="selectin")


class ChitSchedule(Base):
    __tablename__ = "chit_schedules"
    __table_args__ = (UniqueConstraint("group_id", "installment_number", name="uq_chit_schedule_number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("chit_groups.id", ondelete="CASCADE"), index=True, nullable=False)
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    installment_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    dividend: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    payable_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    receivable_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    group: Mapped[ChitGroup] = relationship(back_populates="schedules")


class ChitEnrollment(Base):
    __tablename__ = "chit_enrollments"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("chit_groups.id", ondelete="CASCADE"), index=True, nullable=False)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="RESTRICT"), index=True, nullable=False)
    start_installment: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    end_installment: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    replaced_enrollment_id: Mapped[int | None] = mapped_column(ForeignKey("chit_enrollments.id", ondelete="SET NULL"), nullable=True)
    break_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    group: Mapped[ChitGroup] = relationship(back_populates="enrollments")


class ChitEnrollmentTransfer(Base):
    __tablename__ = "chit_enrollment_transfers"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("chit_groups.id", ondelete="RESTRICT"), index=True, nullable=False)
    old_enrollment_id: Mapped[int] = mapped_column(ForeignKey("chit_enrollments.id", ondelete="RESTRICT"), index=True, nullable=False)
    replacement_member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="RESTRICT"), index=True, nullable=False)
    new_enrollment_id: Mapped[int | None] = mapped_column(ForeignKey("chit_enrollments.id", ondelete="RESTRICT"), nullable=True)
    effective_installment: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    outstanding_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    old_member_acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    new_member_acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    old_member_consent_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    old_member_consent_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    new_member_consent_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    new_member_consent_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ChitPayment(Base):
    __tablename__ = "chit_payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("chit_enrollments.id", ondelete="CASCADE"), index=True, nullable=False)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("chit_schedules.id", ondelete="CASCADE"), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    received_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    late_fee_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    penalty_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    waiver_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    waiver_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    excess_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    refunded_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    collection_location_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    collection_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    collection_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    receipt_number: Mapped[str | None] = mapped_column(String(40), unique=True, index=True, nullable=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True)
    collected_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    payment_source: Mapped[str] = mapped_column(String(30), default="manual", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="posted", nullable=False)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reversed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ChitAuction(Base):
    __tablename__ = "chit_auctions"
    __table_args__ = (UniqueConstraint("schedule_id", name="uq_chit_auction_schedule"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("chit_groups.id", ondelete="CASCADE"), index=True, nullable=False)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("chit_schedules.id", ondelete="CASCADE"), index=True, nullable=False)
    winner_enrollment_id: Mapped[int] = mapped_column(ForeignKey("chit_enrollments.id", ondelete="CASCADE"), index=True, nullable=False)
    auction_date: Mapped[date] = mapped_column(Date, nullable=False)
    bid_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    commission_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    commission_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    dividend_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    payout_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    settled_installment_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    net_payout_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    voucher_number: Mapped[str | None] = mapped_column(String(40), unique=True, index=True, nullable=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True)
    settled_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    winner_acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approval_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payout_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payout_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    payout_reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payout_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payout_verified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    settlement_proof_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    settlement_proof_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reversed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuctionBid(Base):
    __tablename__ = "auction_bids"
    id: Mapped[int] = mapped_column(primary_key=True)
    auction_id: Mapped[int] = mapped_column(ForeignKey("chit_auctions.id", ondelete="RESTRICT"), index=True, nullable=False)
    bidder_enrollment_id: Mapped[int] = mapped_column(ForeignKey("chit_enrollments.id", ondelete="RESTRICT"), index=True, nullable=False)
    bid_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_winning_bid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    recorded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PaymentRefund(Base):
    __tablename__ = "payment_refunds"
    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("chit_payments.id", ondelete="RESTRICT"), index=True, nullable=False)
    refund_number: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    refund_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    refund_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="posted", nullable=False)
    posted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ChitGroupClosure(Base):
    __tablename__ = "chit_group_closures"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("chit_groups.id", ondelete="RESTRICT"), unique=True, nullable=False)
    expected_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    collected_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    auction_settled_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    outstanding_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    expected_closing_balance: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    actual_closing_balance: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    variance_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    variance_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    closed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("chit_groups.id", ondelete="RESTRICT"), index=True, nullable=True)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id", ondelete="RESTRICT"), index=True, nullable=True)
    source_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False)
    account_code: Mapped[str] = mapped_column(String(60), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_reversal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reverses_entry_id: Mapped[int | None] = mapped_column(ForeignKey("ledger_entries.id", ondelete="RESTRICT"), nullable=True)
    posted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
