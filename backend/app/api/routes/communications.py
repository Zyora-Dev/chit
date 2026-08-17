from datetime import UTC,datetime
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import func,select,update
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import require_owner
from app.api.routes.members import require_company
from app.db.session import get_db
from app.models.communication import CommunicationSettings,InAppNotification
from app.models.user import User
from app.schemas.communication import CommunicationSettingsUpdate,NotificationRead,WhatsAppTemplateTest
from app.services.audit import add_audit
from app.services.communications import encrypt_secret,get_communication_settings,meta_configuration_status,send_whatsapp_template

router=APIRouter(prefix="/api/v1/communications",tags=["Communications"])
@router.get("/settings")
async def communication_settings(user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);config=await get_communication_settings(db,company,True,user.id);await db.commit();status=await meta_configuration_status(config);return {"admin_email":config.admin_email,"email_payment_notifications":config.email_payment_notifications,**status}
@router.put("/settings")
async def update_communication_settings(payload:CommunicationSettingsUpdate,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);config=await get_communication_settings(db,company,True,user.id);config.admin_email=str(payload.admin_email).lower() if payload.admin_email else None;config.email_payment_notifications=payload.email_payment_notifications;config.whatsapp_enabled=payload.whatsapp_enabled;config.whatsapp_phone_number_id=payload.whatsapp_phone_number_id.strip() if payload.whatsapp_phone_number_id else None;config.whatsapp_business_account_id=payload.whatsapp_business_account_id.strip() if payload.whatsapp_business_account_id else None;config.whatsapp_api_version=payload.whatsapp_api_version;config.updated_by_user_id=user.id
    if payload.whatsapp_access_token and payload.whatsapp_access_token.strip():config.whatsapp_access_token_encrypted=encrypt_secret(payload.whatsapp_access_token.strip())
    if config.whatsapp_enabled and (not config.whatsapp_phone_number_id or not config.whatsapp_access_token_encrypted):raise HTTPException(status_code=400,detail="Phone Number ID and access token are required before enabling WhatsApp")
    await db.commit();status=await meta_configuration_status(config);return {"admin_email":config.admin_email,"email_payment_notifications":config.email_payment_notifications,**status}
@router.post("/whatsapp/test-template")
async def test_whatsapp_template(payload:WhatsAppTemplateTest,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);config=await get_communication_settings(db,company)
    if not config:raise HTTPException(status_code=400,detail="WhatsApp settings are not configured")
    try:result=await send_whatsapp_template(config,recipient=payload.recipient,template_name=payload.template_name,language_code=payload.language_code)
    except HTTPException:raise
    except Exception as error:
        detail="Meta rejected the template message"
        if hasattr(error,"response"):
            try:detail=error.response.json().get("error",{}).get("message",detail)
            except Exception:pass
        raise HTTPException(status_code=502,detail=detail) from error
    message_id=(result.get("messages") or [{}])[0].get("id")
    add_audit(db,company_id=company.id,user_id=user.id,action="whatsapp.template_test",entity_type="communication_settings",entity_id=config.id,description=f"Sent WhatsApp template {payload.template_name} to a test recipient",new_values={"recipient":payload.recipient[-4:].rjust(len(payload.recipient),"*"),"template_name":payload.template_name,"language_code":payload.language_code,"message_id":message_id})
    await db.commit();return {"status":"accepted","message_id":message_id,"recipient":payload.recipient,"template_name":payload.template_name,"language_code":payload.language_code}
@router.get("/notifications")
async def list_notifications(unread_only:bool=False,limit:int=50,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);query=select(InAppNotification).where(InAppNotification.company_id==company.id,InAppNotification.user_id==user.id)
    if unread_only:query=query.where(InAppNotification.read_at.is_(None))
    rows=list((await db.execute(query.order_by(InAppNotification.created_at.desc()).limit(max(1,min(limit,100))))).scalars().all());unread=await db.scalar(select(func.count(InAppNotification.id)).where(InAppNotification.company_id==company.id,InAppNotification.user_id==user.id,InAppNotification.read_at.is_(None)))
    return {"unread_count":unread or 0,"items":[{"id":row.id,"type":row.notification_type,"title":row.title,"message":row.message,"href":row.href,"entity_type":row.entity_type,"entity_id":row.entity_id,"read_at":row.read_at,"created_at":row.created_at} for row in rows]}
@router.post("/notifications/read")
async def mark_notifications_read(payload:NotificationRead,user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);query=update(InAppNotification).where(InAppNotification.company_id==company.id,InAppNotification.user_id==user.id,InAppNotification.read_at.is_(None))
    if payload.notification_ids:query=query.where(InAppNotification.id.in_(payload.notification_ids))
    await db.execute(query.values(read_at=datetime.now(UTC)));await db.commit();return {"status":"read"}
@router.post("/notifications/read-all")
async def mark_all_read(user:User=Depends(require_owner),db:AsyncSession=Depends(get_db)):
    company=await require_company(db,user.id);await db.execute(update(InAppNotification).where(InAppNotification.company_id==company.id,InAppNotification.user_id==user.id,InAppNotification.read_at.is_(None)).values(read_at=datetime.now(UTC)));await db.commit();return {"status":"read"}
