import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.company import Company
from app.models.rbac import CompanyUser
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = int(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise unauthorized from exc

    user = await db.get(User, user_id)
    if user is None or not user.is_verified or not user.is_active:
        raise unauthorized
    return user


async def require_owner(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access is required",
        )
    return current_user


def get_company_access(permission_code: str):
    async def dependency(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        if current_user.role == "owner":
            company = await db.scalar(select(Company).where(Company.owner_id == current_user.id))
            if company is None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Complete company onboarding first")
            return company, current_user, None
        link = await db.scalar(select(CompanyUser).where(CompanyUser.user_id == current_user.id, CompanyUser.is_active.is_(True)))
        if link is None or not link.role.is_active or permission_code not in {permission.code for permission in link.role.permissions}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        company = await db.get(Company, link.company_id)
        if company is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Company access unavailable")
        return company, current_user, link.branch_id

    return dependency
