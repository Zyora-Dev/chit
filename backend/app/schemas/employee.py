from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, EmailStr, Field, field_validator


class EmployeeSalaryCreate(BaseModel):
    effective_from:date; annual_ctc:Decimal=Field(default=0,ge=0); basic:Decimal=Field(default=0,ge=0); hra:Decimal=Field(default=0,ge=0); allowances:Decimal=Field(default=0,ge=0); incentives:Decimal=Field(default=0,ge=0); employee_pf:Decimal=Field(default=0,ge=0); employee_esi:Decimal=Field(default=0,ge=0); professional_tax:Decimal=Field(default=0,ge=0); tds:Decimal=Field(default=0,ge=0); other_deductions:Decimal=Field(default=0,ge=0); notes:str|None=None


class EmployeeCreate(BaseModel):
    branch_id:int|None=None; full_name:str=Field(min_length=2,max_length=200); father_or_spouse_name:str|None=None
    date_of_birth:date|None=None; gender:str|None=Field(default=None,pattern=r"^(male|female|other|prefer_not_to_say)$"); marital_status:str|None=None; blood_group:str|None=None
    mobile_number:str=Field(pattern=r"^\+?[1-9]\d{7,14}$"); alternate_mobile_number:str|None=None; personal_email:EmailStr|None=None; official_email:EmailStr|None=None
    current_address:str=Field(min_length=5,max_length=1000); permanent_address:str|None=None
    department:str=Field(pattern=r"^(HR|Admin|Sales|Collection)$"); designation:str=Field(pattern=r"^(Manager|Supervisor|Agent|Executive|Security|Office Boy)$")
    employment_type:str=Field(pattern=r"^(permanent|probation|contract|part_time|temporary|intern)$"); work_mode:str=Field(default="office",pattern=r"^(office|field|hybrid|remote)$")
    joining_date:date; probation_end_date:date|None=None; reporting_manager_employee_id:int|None=None; collection_agent_enabled:bool=False; status:str=Field(default="active",pattern=r"^(active|on_leave|suspended|separated)$")
    emergency_contact_name:str=Field(min_length=2,max_length=200); emergency_contact_relationship:str=Field(min_length=2,max_length=80); emergency_contact_mobile:str=Field(pattern=r"^\+?[1-9]\d{7,14}$"); emergency_contact_address:str|None=None
    nominee_name:str|None=None; nominee_relationship:str|None=None; nominee_date_of_birth:date|None=None; nominee_mobile_number:str|None=None; nominee_address:str|None=None; nominee_share_percent:Decimal=Field(default=100,ge=0,le=100)
    bank_account_holder_name:str|None=None; bank_account_number:str|None=Field(default=None,min_length=6,max_length=34,pattern=r"^[A-Za-z0-9]+$"); bank_name:str|None=None; bank_branch_name:str|None=None; bank_ifsc_code:str|None=Field(default=None,pattern=r"^[A-Za-z]{4}0[A-Za-z0-9]{6}$"); bank_account_type:str|None=Field(default=None,pattern=r"^(savings|current|other)$")
    aadhaar_number:str|None=None; pan:str|None=Field(default=None,pattern=r"^[A-Za-z]{5}[0-9]{4}[A-Za-z]$"); uan:str|None=Field(default=None,pattern=r"^\d{12}$"); pf_member_id:str|None=None; esic_ip_number:str|None=Field(default=None,pattern=r"^\d{10}$")
    professional_tax_applicable:bool=False; labour_welfare_fund_applicable:bool=False; tax_regime:str=Field(default="new",pattern=r"^(old|new)$"); internal_notes:str|None=Field(default=None,max_length=1000); salary:EmployeeSalaryCreate|None=None
    @field_validator("aadhaar_number")
    @classmethod
    def aadhaar(cls,value):
        if not value:return None
        normalized="".join(ch for ch in value if ch.isdigit())
        if len(normalized)!=12:raise ValueError("Aadhaar must contain 12 digits")
        return normalized
    @field_validator("pan","bank_ifsc_code")
    @classmethod
    def uppercase(cls,value):return value.upper() if value else None


class EmployeeUpdate(EmployeeCreate):
    aadhaar_number:str|None=None


class EmployeeKycReview(BaseModel):
    aadhaar_status:str=Field(pattern=r"^(verified|rejected|not_applicable)$"); pan_status:str=Field(pattern=r"^(verified|rejected|not_applicable)$"); bank_status:str=Field(pattern=r"^(verified|rejected|not_applicable)$"); notes:str|None=None; rejection_reason:str|None=None


class EmployeeResponse(BaseModel):
    id:int; employee_code:str; branch_id:int|None; full_name:str; father_or_spouse_name:str|None; date_of_birth:date|None; gender:str|None; marital_status:str|None; blood_group:str|None; mobile_number:str; alternate_mobile_number:str|None; personal_email:EmailStr|None; official_email:EmailStr|None; current_address:str; permanent_address:str|None; department:str; designation:str; employment_type:str; work_mode:str; joining_date:date; probation_end_date:date|None; reporting_manager_employee_id:int|None; collection_agent_enabled:bool; status:str; emergency_contact_name:str; emergency_contact_relationship:str; emergency_contact_mobile:str; emergency_contact_address:str|None; nominee_name:str|None; nominee_relationship:str|None; nominee_date_of_birth:date|None; nominee_mobile_number:str|None; nominee_address:str|None; nominee_share_percent:Decimal; bank_account_holder_name:str|None; bank_account_number:str|None; bank_name:str|None; bank_branch_name:str|None; bank_ifsc_code:str|None; bank_account_type:str|None; aadhaar_last4:str|None; pan:str|None; uan:str|None; pf_member_id:str|None; esic_ip_number:str|None; professional_tax_applicable:bool; labour_welfare_fund_applicable:bool; tax_regime:str; kyc_status:str; aadhaar_verification_status:str; pan_verification_status:str; bank_verification_status:str; kyc_reviewed_at:datetime|None; kyc_rejection_reason:str|None; kyc_notes:str|None; internal_notes:str|None; is_active:bool; archive_reason:str|None; created_at:datetime
    model_config={"from_attributes":True}


class EmployeeListResponse(BaseModel):
    items:list[EmployeeResponse]; total:int; page:int; page_size:int
