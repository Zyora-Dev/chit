from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_owner
from app.api.routes.members import require_company
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.advance import AuditLogResponse

router = APIRouter(prefix="/api/v1/audit-logs", tags=["Audit History"])


@router.get("", response_model=list[AuditLogResponse])
async def list_audit_logs(
    action: str | None = Query(default=None, max_length=80),
    entity_type: str | None = Query(default=None, max_length=80),
    date_from: date | None = None, date_to: date | None = None,
    user: User = Depends(require_owner), db: AsyncSession = Depends(get_db),
):
    company = await require_company(db, user.id)
    query = select(AuditLog, User.email).outerjoin(User, AuditLog.user_id == User.id).where(AuditLog.company_id == company.id)
    if action: query = query.where(AuditLog.action == action)
    if entity_type: query = query.where(AuditLog.entity_type == entity_type)
    if date_from: query = query.where(AuditLog.created_at >= datetime.combine(date_from, time.min))
    if date_to: query = query.where(AuditLog.created_at <= datetime.combine(date_to, time.max))
    records = (await db.execute(query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(1000))).all()
    return [
        {
            "id": log.id, "user_id": log.user_id, "actor_email": actor_email,
            "action": log.action, "entity_type": log.entity_type, "entity_id": log.entity_id,
            "description": log.description, "old_values": log.old_values, "new_values": log.new_values,
            "ip_address": log.ip_address, "user_agent": log.user_agent, "created_at": log.created_at,
        }
        for log, actor_email in records
    ]
