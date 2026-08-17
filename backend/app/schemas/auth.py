from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3,max_length=320)
    password: str = Field(min_length=8, max_length=128)


class MfaVerifyRequest(BaseModel):
    challenge_token: str = Field(min_length=32, max_length=256)
    code: str = Field(min_length=6, max_length=32)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class MfaPasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)


class MfaConfirmRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class MfaDisableRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    code: str = Field(min_length=6, max_length=32)


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{6}$")


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str


class TokenResponse(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    mfa_required: bool = False
    challenge_token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class CurrentUserResponse(BaseModel):
    id: int; email: EmailStr; role: str
