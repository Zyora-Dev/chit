from pydantic import BaseModel,Field
class RoleCreate(BaseModel):name:str=Field(min_length=2,max_length=100);description:str|None=None;permission_codes:list[str]=Field(default_factory=list)
class UserCredentialCreate(BaseModel):employee_id:int;role_id:int;branch_id:int|None=None;password:str=Field(min_length=8,max_length=128)
class PasswordReset(BaseModel):password:str=Field(min_length=8,max_length=128)
class UserStatus(BaseModel):is_active:bool
