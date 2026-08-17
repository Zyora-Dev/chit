from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class BranchCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    mobile_number: str | None = Field(default=None, pattern=r"^\+?[1-9]\d{7,14}$")
    email: EmailStr | None = None
    manager_name: str | None = Field(default=None, max_length=200)
    address_line_1: str = Field(min_length=3, max_length=250)
    address_line_2: str | None = Field(default=None, max_length=250)
    locality: str | None = Field(default=None, max_length=150)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    postal_code: str = Field(pattern=r"^[A-Za-z0-9 -]{3,12}$")
    country: str = Field(default="India", min_length=2, max_length=100)
    landmark: str | None = Field(default=None, max_length=200)


class BranchUpdate(BranchCreate):
    is_active: bool = True


class BranchResponse(BranchUpdate):
    id: int
    branch_code: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
