from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdvancePayment(Base):
    __tablename__ = "advance_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("chit_groups.id", ondelete="CASCADE"), index=True, nullable=False)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("chit_enrollments.id", ondelete="CASCADE"), index=True, nullable=False)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    receipt_number: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="available", nullable=False)
    received_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AdvanceAllocation(Base):
    __tablename__ = "advance_allocations"

    id: Mapped[int] = mapped_column(primary_key=True)
    advance_payment_id: Mapped[int] = mapped_column(ForeignKey("advance_payments.id", ondelete="CASCADE"), index=True, nullable=False)
    payment_id: Mapped[int] = mapped_column(ForeignKey("chit_payments.id", ondelete="RESTRICT"), unique=True, nullable=False)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("chit_schedules.id", ondelete="RESTRICT"), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    allocated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
