from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


EXPENSE_CATEGORIES = ("food", "petrol_allowance", "snacks", "broadband_bill", "courier_bill", "recharge", "others")


class ExpenseBase(BaseModel):
    expense_date: date
    category: str
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    branch_id: int | None = None
    payee: str | None = Field(default=None, max_length=200)
    payment_mode: str = Field(pattern=r"^(cash|upi|bank|cheque|card)$")
    reference_number: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=2, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        if value not in EXPENSE_CATEGORIES:
            raise ValueError("Invalid expense category")
        return value


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(ExpenseBase):
    pass


class ExpenseResponse(ExpenseBase):
    id: int
    branch_name: str | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class ExpenseListResponse(BaseModel):
    items: list[ExpenseResponse]
    total_amount: Decimal
    count: int
    category_totals: dict[str, Decimal]
