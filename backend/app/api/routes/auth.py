from datetime import UTC, datetime, timedelta
import base64
import hashlib
import io
import json
import secrets

import httpx
import pyotp
import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.api.dependencies import get_current_user
from app.core.security import (
    create_access_token,
    decrypt_mfa_secret,
    encrypt_mfa_secret,
    generate_recovery_codes,
    generate_otp,
    hash_recovery_code,
    hash_otp,
    hash_password,
    verify_otp_hash,
    verify_password,
    verify_totp,
)
from app.db.session import get_db
from app.models.otp import EmailOTP
from app.models.session import AuthAttempt, AuthSession, MfaChallenge
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MfaConfirmRequest,
    MfaDisableRequest,
    MfaPasswordRequest,
    MfaVerifyRequest,
    MessageResponse,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    RefreshRequest,
    PasswordChangeRequest,
    CurrentUserResponse,
    VerifyEmailRequest,
)
from app.services.email import EmailConfigurationError, send_otp_email

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


def token_digest(value:str)->str:
    return hashlib.sha256(value.encode()).hexdigest()


async def enforce_rate_limit(db:AsyncSession,identifier:str,ip_address:str,action:str,limit:int,minutes:int)->None:
    since=datetime.now(UTC)-timedelta(minutes=minutes);count=await db.scalar(select(func.count(AuthAttempt.id)).where(AuthAttempt.identifier==identifier,AuthAttempt.ip_address==ip_address,AuthAttempt.action==action,AuthAttempt.successful.is_(False),AuthAttempt.created_at>=since))
    if count>=limit: raise HTTPException(status_code=429,detail="Too many attempts. Try again later.",headers={"Retry-After":str(minutes*60)})


def issue_refresh_session(db:AsyncSession,user:User,request:Request)->str:
    token=secrets.token_urlsafe(48);db.add(AuthSession(user_id=user.id,token_hash=token_digest(token),family_id=secrets.token_hex(16),ip_address=request.client.host if request.client else None,user_agent=request.headers.get("user-agent","")[:500] or None,expires_at=datetime.now(UTC)+timedelta(days=settings.refresh_token_expire_days)));return token


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    identifier=normalize_email(email);result = await db.execute(select(User).where((User.email == identifier)|(User.login_id == email.strip().upper())))
    return result.scalar_one_or_none()


async def issue_otp(db: AsyncSession, user: User, purpose: str, request:Request|None=None) -> None:
    now = datetime.now(UTC)
    if request:
        ip=request.client.host if request.client else "unknown";await enforce_rate_limit(db,user.email,ip,f"otp:{purpose}",settings.otp_send_limit,settings.otp_send_window_minutes);db.add(AuthAttempt(identifier=user.email,ip_address=ip,action=f"otp:{purpose}",successful=False))
    await db.execute(
        update(EmailOTP)
        .where(
            EmailOTP.user_id == user.id,
            EmailOTP.purpose == purpose,
            EmailOTP.used_at.is_(None),
        )
        .values(used_at=now)
    )
    code = generate_otp()
    db.add(
        EmailOTP(
            user_id=user.id,
            purpose=purpose,
            code_hash=hash_otp(code),
            expires_at=now + timedelta(minutes=settings.otp_expire_minutes),
        )
    )
    await send_otp_email(user.email, code, purpose)


async def consume_otp(
    db: AsyncSession, user: User, code: str, purpose: str
) -> EmailOTP | None:
    result = await db.execute(
        select(EmailOTP)
        .where(
            EmailOTP.user_id == user.id,
            EmailOTP.purpose == purpose,
            EmailOTP.used_at.is_(None),
        )
        .order_by(EmailOTP.created_at.desc())
        .limit(1)
    )
    otp = result.scalar_one_or_none()
    if otp is None or otp.expires_at <= datetime.now(UTC):
        return None
    if not verify_otp_hash(code, otp.code_hash):
        return None
    otp.used_at = datetime.now(UTC)
    return otp


def email_service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, EmailConfigurationError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service is not configured",
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Unable to send verification email",
    )


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request:Request, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    email = normalize_email(payload.email)
    if await get_user_by_email(db, email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        await db.flush()
        await issue_otp(db, user, "email_verification",request)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from exc
    except (EmailConfigurationError, httpx.HTTPError) as exc:
        await db.rollback()
        raise email_service_error(exc) from exc

    return MessageResponse(message="Registration successful. Check your email for the OTP.")


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    user = await get_user_by_email(db, payload.email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")
    if user.is_verified:
        return MessageResponse(message="Email is already verified.")
    if await consume_otp(db, user, payload.otp, "email_verification") is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

    user.is_verified = True
    await db.commit()
    return MessageResponse(message="Email verified successfully.")


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    payload: ResendVerificationRequest, request:Request, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    user = await get_user_by_email(db, payload.email)
    if user is None or user.is_verified:
        return MessageResponse(message="If verification is required, an OTP has been sent.")
    try:
        await issue_otp(db, user, "email_verification",request)
        await db.commit()
    except (EmailConfigurationError, httpx.HTTPError) as exc:
        await db.rollback()
        raise email_service_error(exc) from exc
    return MessageResponse(message="If verification is required, an OTP has been sent.")


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request:Request, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    email=normalize_email(payload.email);ip=request.client.host if request.client else "unknown";await enforce_rate_limit(db,email,ip,"login",settings.login_attempt_limit,settings.login_attempt_window_minutes)
    user = await get_user_by_email(db, payload.email)
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        db.add(AuthAttempt(identifier=email,ip_address=ip,action="login",successful=False));await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email is not verified")
    db.add(AuthAttempt(identifier=email,ip_address=ip,action="login",successful=True))
    if user.mfa_enabled:
        challenge=secrets.token_urlsafe(48);db.add(MfaChallenge(user_id=user.id,challenge_hash=token_digest(challenge),ip_address=ip,user_agent=request.headers.get("user-agent","")[:500] or None,expires_at=datetime.now(UTC)+timedelta(minutes=5)));await db.commit();return TokenResponse(mfa_required=True,challenge_token=challenge)
    refresh=issue_refresh_session(db,user,request);await db.commit();return TokenResponse(access_token=create_access_token(user.id, user.role),refresh_token=refresh)


@router.post("/mfa/verify-login",response_model=TokenResponse)
async def verify_mfa_login(payload:MfaVerifyRequest,request:Request,db:AsyncSession=Depends(get_db)):
    challenge=await db.scalar(select(MfaChallenge).where(MfaChallenge.challenge_hash==token_digest(payload.challenge_token),MfaChallenge.used_at.is_(None)))
    if not challenge or challenge.expires_at<=datetime.now(UTC):raise HTTPException(status_code=401,detail="MFA challenge expired. Sign in again.")
    user=await db.get(User,challenge.user_id)
    if not user or not user.mfa_enabled or not user.mfa_secret_encrypted:raise HTTPException(status_code=401,detail="MFA is not available for this account")
    valid=verify_totp(decrypt_mfa_secret(user.mfa_secret_encrypted),payload.code);hashes=json.loads(user.mfa_recovery_codes_hash or "[]")
    if not valid:
        code_hash=hash_recovery_code(payload.code)
        if code_hash in hashes:hashes.remove(code_hash);user.mfa_recovery_codes_hash=json.dumps(hashes);valid=True
    if not valid:raise HTTPException(status_code=401,detail="Invalid authenticator or recovery code")
    challenge.used_at=datetime.now(UTC);refresh=issue_refresh_session(db,user,request);await db.commit();return TokenResponse(access_token=create_access_token(user.id,user.role),refresh_token=refresh)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    payload: ForgotPasswordRequest, request:Request, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    user = await get_user_by_email(db, payload.email)
    if user is not None:
        try:
            await issue_otp(db, user, "password_reset",request)
            await db.commit()
        except (EmailConfigurationError, httpx.HTTPError) as exc:
            await db.rollback()
            raise email_service_error(exc) from exc
    return MessageResponse(message="If the account exists, a password reset OTP has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    user = await get_user_by_email(db, payload.email)
    if user is None or await consume_otp(db, user, payload.otp, "password_reset") is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

    user.password_hash = hash_password(payload.new_password)
    await db.execute(update(AuthSession).where(AuthSession.user_id==user.id,AuthSession.revoked_at.is_(None)).values(revoked_at=datetime.now(UTC)))
    await db.commit()
    return MessageResponse(message="Password reset successfully.")


@router.post("/refresh",response_model=TokenResponse)
async def refresh_session(payload:RefreshRequest,request:Request,db:AsyncSession=Depends(get_db)):
    session=await db.scalar(select(AuthSession).where(AuthSession.token_hash==token_digest(payload.refresh_token)))
    if not session or session.revoked_at or session.expires_at<=datetime.now(UTC): raise HTTPException(status_code=401,detail="Invalid refresh token")
    user=await db.get(User,session.user_id);session.revoked_at=datetime.now(UTC);session.last_used_at=datetime.now(UTC);refresh=issue_refresh_session(db,user,request);await db.commit();return TokenResponse(access_token=create_access_token(user.id,user.role),refresh_token=refresh)


@router.post("/logout",response_model=MessageResponse)
async def logout(payload:RefreshRequest,db:AsyncSession=Depends(get_db)):
    session=await db.scalar(select(AuthSession).where(AuthSession.token_hash==token_digest(payload.refresh_token))); 
    if session: session.revoked_at=datetime.now(UTC);await db.commit()
    return MessageResponse(message="Logged out successfully.")


@router.get("/me",response_model=CurrentUserResponse)
async def current_user(user:User=Depends(get_current_user)):
    return user


@router.get("/security")
async def security_status(user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    active=await db.scalar(select(func.count(AuthSession.id)).where(AuthSession.user_id==user.id,AuthSession.revoked_at.is_(None),AuthSession.expires_at>datetime.now(UTC)));recovery_count=len(json.loads(user.mfa_recovery_codes_hash or "[]"));return {"email":user.email,"role":user.role,"mfa_enabled":user.mfa_enabled,"mfa_enabled_at":user.mfa_enabled_at,"recovery_codes_remaining":recovery_count,"active_sessions":active,"password_updated_at":user.updated_at}


@router.post("/change-password",response_model=MessageResponse)
async def change_password(payload:PasswordChangeRequest,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    if not verify_password(payload.current_password,user.password_hash):raise HTTPException(status_code=400,detail="Current password is incorrect")
    if verify_password(payload.new_password,user.password_hash):raise HTTPException(status_code=400,detail="New password must be different")
    user.password_hash=hash_password(payload.new_password);await db.execute(update(AuthSession).where(AuthSession.user_id==user.id,AuthSession.revoked_at.is_(None)).values(revoked_at=datetime.now(UTC)));await db.commit();return MessageResponse(message="Password changed. Sign in again on all devices.")


@router.post("/mfa/setup")
async def setup_mfa(payload:MfaPasswordRequest,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    if not verify_password(payload.current_password,user.password_hash):raise HTTPException(status_code=400,detail="Current password is incorrect")
    if user.mfa_enabled:raise HTTPException(status_code=409,detail="Two-factor authentication is already enabled")
    secret=pyotp.random_base32();user.mfa_secret_encrypted=encrypt_mfa_secret(secret);user.mfa_recovery_codes_hash=None;uri=pyotp.TOTP(secret).provisioning_uri(name=user.email,issuer_name="zChit");image=qrcode.make(uri);buffer=io.BytesIO();image.save(buffer,format="PNG");await db.commit();return {"secret":secret,"otpauth_uri":uri,"qr_code_data_url":f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"}


@router.post("/mfa/confirm")
async def confirm_mfa(payload:MfaConfirmRequest,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    if user.mfa_enabled:raise HTTPException(status_code=409,detail="Two-factor authentication is already enabled")
    if not user.mfa_secret_encrypted or not verify_totp(decrypt_mfa_secret(user.mfa_secret_encrypted),payload.code):raise HTTPException(status_code=400,detail="Invalid authenticator code")
    codes=generate_recovery_codes();user.mfa_enabled=True;user.mfa_enabled_at=datetime.now(UTC);user.mfa_recovery_codes_hash=json.dumps([hash_recovery_code(code) for code in codes]);await db.commit();return {"message":"Two-factor authentication enabled","recovery_codes":codes}


@router.post("/mfa/recovery-codes")
async def regenerate_recovery_codes(payload:MfaPasswordRequest,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    if not user.mfa_enabled:raise HTTPException(status_code=409,detail="Enable two-factor authentication first")
    if not verify_password(payload.current_password,user.password_hash):raise HTTPException(status_code=400,detail="Current password is incorrect")
    codes=generate_recovery_codes();user.mfa_recovery_codes_hash=json.dumps([hash_recovery_code(code) for code in codes]);await db.commit();return {"recovery_codes":codes}


@router.post("/mfa/disable",response_model=MessageResponse)
async def disable_mfa(payload:MfaDisableRequest,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    if not user.mfa_enabled or not user.mfa_secret_encrypted:raise HTTPException(status_code=409,detail="Two-factor authentication is not enabled")
    if not verify_password(payload.current_password,user.password_hash):raise HTTPException(status_code=400,detail="Current password is incorrect")
    if not verify_totp(decrypt_mfa_secret(user.mfa_secret_encrypted),payload.code):raise HTTPException(status_code=400,detail="Invalid authenticator code")
    user.mfa_enabled=False;user.mfa_secret_encrypted=None;user.mfa_recovery_codes_hash=None;user.mfa_enabled_at=None;await db.execute(update(AuthSession).where(AuthSession.user_id==user.id,AuthSession.revoked_at.is_(None)).values(revoked_at=datetime.now(UTC)));await db.commit();return MessageResponse(message="Two-factor authentication disabled. Sign in again.")


@router.get("/sessions")
async def list_sessions(user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    sessions=list((await db.execute(select(AuthSession).where(AuthSession.user_id==user.id,AuthSession.revoked_at.is_(None),AuthSession.expires_at>datetime.now(UTC)).order_by(AuthSession.created_at.desc()))).scalars().all());return [{"id":item.id,"ip_address":item.ip_address,"user_agent":item.user_agent,"created_at":item.created_at,"last_used_at":item.last_used_at,"expires_at":item.expires_at} for item in sessions]


@router.delete("/sessions/{session_id}",response_model=MessageResponse)
async def revoke_session(session_id:int,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    session=await db.scalar(select(AuthSession).where(AuthSession.id==session_id,AuthSession.user_id==user.id,AuthSession.revoked_at.is_(None)))
    if not session:raise HTTPException(status_code=404,detail="Active session not found")
    session.revoked_at=datetime.now(UTC);await db.commit();return MessageResponse(message="Session revoked")


@router.post("/sessions/revoke-all",response_model=MessageResponse)
async def revoke_all_sessions(user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    await db.execute(update(AuthSession).where(AuthSession.user_id==user.id,AuthSession.revoked_at.is_(None)).values(revoked_at=datetime.now(UTC)));await db.commit();return MessageResponse(message="All sessions revoked")
