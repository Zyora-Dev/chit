from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class AdvancePaymentCreate(BaseModel):
    group_id: int
    member_id: int
    branch_id: int | None = None
    amount: Decimal = Field(gt=0)
    payment_date: date
    payment_mode: str = Field(pattern=r"^(cash|upi|bank|cheque)$")
    reference_number: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)


class AdvanceAllocate(BaseModel):
    schedule_ids: list[int] | None = None


class AdvancePaymentResponse(BaseModel):
    id: int; group_id: int; group_code: str; scheme_name: str
    member_id: int; member_code: str; member_name: str; mobile_number: str
    receipt_number: str; amount: Decimal; allocated_amount: Decimal; available_amount: Decimal
    payment_date: date; payment_mode: str; reference_number: str | None; status: str
    created_at: datetime


class AuditLogResponse(BaseModel):
    id: int; user_id: int | None; actor_email: str | None = None
    action: str; entity_type: str; entity_id: int | None
    description: str; old_values: dict | None; new_values: dict | None
    ip_address: str | None; user_agent: str | None; created_at: datetime
    model_config = {"from_attributes": True}
