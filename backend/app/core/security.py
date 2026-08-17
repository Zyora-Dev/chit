import hashlib
import hmac
import secrets
import base64
from datetime import UTC, datetime, timedelta

import jwt
import pyotp
from cryptography.fernet import Fernet
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()


def _mfa_cipher() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.jwt_secret_key.encode()).digest())
    return Fernet(key)


def encrypt_mfa_secret(secret: str) -> str:
    return _mfa_cipher().encrypt(secret.encode()).decode()


def decrypt_mfa_secret(value: str) -> str:
    return _mfa_cipher().decrypt(value.encode()).decode()


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code.replace(" ", ""), valid_window=1)


def generate_recovery_codes(count: int = 10) -> list[str]:
    return [f"{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}" for _ in range(count)]


def hash_recovery_code(code: str) -> str:
    normalized = code.strip().upper().replace(" ", "")
    return hmac.new(settings.otp_secret_key.encode(), normalized.encode(), hashlib.sha256).hexdigest()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: int, role: str) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "role": role, "exp": expires_at, "iat": datetime.now(UTC)}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(code: str) -> str:
    return hmac.new(
        settings.otp_secret_key.encode(), code.encode(), hashlib.sha256
    ).hexdigest()


def verify_otp_hash(code: str, code_hash: str) -> bool:
    return hmac.compare_digest(hash_otp(code), code_hash)
