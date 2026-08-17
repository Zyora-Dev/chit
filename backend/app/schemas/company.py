from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator, model_validator


class CompanyAddressCreate(BaseModel):
    address_type: str = Field(default="registered", pattern=r"^(registered|office|branch|billing)$")
    is_primary: bool = False
    address_line_1: str = Field(min_length=3, max_length=250)
    address_line_2: str | None = Field(default=None, max_length=250)
    locality: str | None = Field(default=None, max_length=150)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    postal_code: str = Field(pattern=r"^[A-Za-z0-9 -]{3,12}$")
    country: str = Field(default="India", min_length=2, max_length=100)
    landmark: str | None = Field(default=None, max_length=200)


class CompanyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    legal_name: str | None = Field(default=None, max_length=200)
    mobile_number: str = Field(pattern=r"^\+?[1-9]\d{7,14}$")
    email: EmailStr
    gstin: str | None = None
    pan: str | None = None
    website: HttpUrl | None = None
    addresses: list[CompanyAddressCreate] = Field(min_length=1, max_length=20)

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().upper()
        if len(normalized) != 15 or not normalized.isalnum():
            raise ValueError("GSTIN must contain 15 alphanumeric characters")
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

    @model_validator(mode="after")
    def ensure_one_primary_address(self):
        primary_count = sum(address.is_primary for address in self.addresses)
        if primary_count > 1:
            raise ValueError("Only one address can be primary")
        if primary_count == 0:
            self.addresses[0].is_primary = True
        return self


class CompanyUpdate(CompanyCreate):
    pass


class CompanyAddressResponse(CompanyAddressCreate):
    id: int

    model_config = {"from_attributes": True}


class CompanyResponse(BaseModel):
    id: int
    company_code: str
    name: str
    legal_name: str | None
    mobile_number: str
    email: EmailStr
    gstin: str | None
    pan: str | None
    website: str | None
    logo_url: str | None
    is_active: bool
    addresses: list[CompanyAddressResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LogoResponse(BaseModel):
    logo_url: str
