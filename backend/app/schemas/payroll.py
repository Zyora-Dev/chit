from decimal import Decimal
from pydantic import BaseModel,Field
class PayrollRunCreate(BaseModel):payroll_year:int=Field(ge=2000,le=2100);payroll_month:int=Field(ge=1,le=12);notes:str|None=None
class PayrollDaysUpdate(BaseModel):payable_days:Decimal=Field(ge=0);lop_days:Decimal=Field(ge=0)
class PayrollApproval(BaseModel):approval_notes:str|None=None
