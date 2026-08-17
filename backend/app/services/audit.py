from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


def add_audit(
    db: AsyncSession,
    *,
    company_id: int,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    description: str,
    request: Request | None = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            company_id=company_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            old_values=old_values,
            new_values=new_values,
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent")[:500] if request and request.headers.get("user-agent") else None,
        )
    )
