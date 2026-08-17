from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel,EmailStr,Field
class AgentCreate(BaseModel):employee_id:int;email:EmailStr;password:str=Field(min_length=8,max_length=128)
class AgentStatusUpdate(BaseModel):is_active:bool
class AgentAssignments(BaseModel):group_ids:list[int]=Field(default_factory=list);enrollment_ids:list[int]=Field(default_factory=list)
class LocationPoint(BaseModel):latitude:Decimal=Field(ge=-90,le=90);longitude:Decimal=Field(ge=-180,le=180);accuracy_meters:Decimal|None=Field(default=None,ge=0);device_recorded_at:datetime|None=None
class AgentCollectionCreate(BaseModel):enrollment_id:int;schedule_id:int|None=None;collection_type:str=Field(pattern=r"^(regular|late|advance)$");amount_type:str=Field(default="partial",pattern=r"^(full|partial)$");amount:Decimal=Field(gt=0);payment_mode:str=Field(pattern=r"^(cash|upi|bank|cheque)$");reference_number:str|None=None;notes:str|None=None;latitude:Decimal=Field(ge=-90,le=90);longitude:Decimal=Field(ge=-180,le=180);location_text:str|None=None
