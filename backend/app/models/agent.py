from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CollectionAgent(Base):
    __tablename__ = "collection_agents"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="RESTRICT"), index=True, nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AgentGroupAssignment(Base):
    __tablename__ = "agent_group_assignments"
    __table_args__ = (UniqueConstraint("collection_agent_id", "group_id", name="uq_agent_group_assignment"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="RESTRICT"), index=True, nullable=False)
    collection_agent_id: Mapped[int] = mapped_column(ForeignKey("collection_agents.id", ondelete="CASCADE"), index=True, nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("chit_groups.id", ondelete="RESTRICT"), index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    assigned_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AgentMemberAssignment(Base):
    __tablename__ = "agent_member_assignments"
    __table_args__ = (UniqueConstraint("collection_agent_id", "enrollment_id", name="uq_agent_member_assignment"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="RESTRICT"), index=True, nullable=False)
    collection_agent_id: Mapped[int] = mapped_column(ForeignKey("collection_agents.id", ondelete="CASCADE"), index=True, nullable=False)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("chit_enrollments.id", ondelete="RESTRICT"), index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    assigned_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AgentShift(Base):
    __tablename__ = "agent_shifts"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="RESTRICT"), index=True, nullable=False)
    collection_agent_id: Mapped[int] = mapped_column(ForeignKey("collection_agents.id", ondelete="RESTRICT"), index=True, nullable=False)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True, nullable=False)
    checked_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    check_in_latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    check_in_longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    check_in_accuracy_meters: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    check_out_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)


class AgentLocation(Base):
    __tablename__ = "agent_locations"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="RESTRICT"), index=True, nullable=False)
    collection_agent_id: Mapped[int] = mapped_column(ForeignKey("collection_agents.id", ondelete="RESTRICT"), index=True, nullable=False)
    shift_id: Mapped[int] = mapped_column(ForeignKey("agent_shifts.id", ondelete="CASCADE"), index=True, nullable=False)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    accuracy_meters: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    device_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
