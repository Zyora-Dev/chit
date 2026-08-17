import base64
import hashlib
import html
import logging
from decimal import Decimal
import httpx
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.communication import CommunicationSettings,InAppNotification
from app.models.company import Company
from app.models.user import User

logger=logging.getLogger(__name__)
def _cipher():return Fernet(base64.urlsafe_b64encode(hashlib.sha256((settings.jwt_secret_key+":communications").encode()).digest()))
def encrypt_secret(value:str)->str:return _cipher().encrypt(value.encode()).decode()
def decrypt_secret(value:str)->str:return _cipher().decrypt(value.encode()).decode()
async def get_communication_settings(db:AsyncSession,company:Company,create:bool=False,user_id:int|None=None):
    config=await db.scalar(select(CommunicationSettings).where(CommunicationSettings.company_id==company.id))
    if not config and create:
        config=CommunicationSettings(company_id=company.id,admin_email=company.email,email_payment_notifications=True,updated_by_user_id=user_id);db.add(config);await db.flush()
    return config
async def get_platform_whatsapp_settings(db:AsyncSession):
    return await db.scalar(select(CommunicationSettings).where(CommunicationSettings.whatsapp_enabled.is_(True),CommunicationSettings.whatsapp_phone_number_id.is_not(None),CommunicationSettings.whatsapp_access_token_encrypted.is_not(None)).order_by(CommunicationSettings.id))
def add_notification(db:AsyncSession,*,company_id:int,user_id:int|None,title:str,message:str,notification_type:str,href:str|None=None,entity_type:str|None=None,entity_id:int|None=None):db.add(InAppNotification(company_id=company_id,user_id=user_id,title=title,message=message,notification_type=notification_type,href=href,entity_type=entity_type,entity_id=entity_id))
async def send_transactional_email(recipient:str,subject:str,body_html:str):
    if not settings.zeptomail_send_token or not settings.zeptomail_from_email:raise RuntimeError("ZeptoMail credentials are not configured")
    token=settings.zeptomail_send_token.strip()
    if token.lower().startswith("zoho-enczapikey "):token=token.split(maxsplit=1)[1]
    payload={"from":{"address":settings.zeptomail_from_email,"name":settings.zeptomail_from_name},"to":[{"email_address":{"address":recipient,"name":recipient}}],"subject":subject,"htmlbody":body_html,"track_clicks":False,"track_opens":False}
    async with httpx.AsyncClient(timeout=15) as client:response=await client.post(settings.zeptomail_api_url,json=payload,headers={"Authorization":f"Zoho-enczapikey {token}","Content-Type":"application/json"});response.raise_for_status()
async def notify_payment_collection(db:AsyncSession,*,company:Company,member_name:str,scheme_name:str,amount:Decimal,receipt_number:str,payment_mode:str,source:str,entity_id:int,add_in_app:bool=True,member_mobile:str|None=None,installment_number:int|None=None,collector_name:str|None=None):
    title=f"Payment collected · {member_name}";message=f"₹{amount} received for {scheme_name} via {payment_mode.upper()} · {receipt_number} · {source.replace('_',' ')}"
    if add_in_app:add_notification(db,company_id=company.id,user_id=company.owner_id,title=title,message=message,notification_type="payment",href=f"/dashboard/receipts/{entity_id}",entity_type="payment",entity_id=entity_id)
    config=await get_communication_settings(db,company)
    if config and config.email_payment_notifications and config.admin_email:
        try:await send_transactional_email(config.admin_email,f"zChit payment collected: {receipt_number}",f"<div style='font-family:Arial;color:#0f172a'><h2 style='color:#059669'>Payment collected</h2><p><b>Member:</b> {html.escape(member_name)}</p><p><b>Scheme:</b> {html.escape(scheme_name)}</p><p><b>Amount:</b> ₹{amount}</p><p><b>Mode:</b> {html.escape(payment_mode.upper())}</p><p><b>Receipt:</b> {html.escape(receipt_number)}</p><p><b>Source:</b> {html.escape(source.replace('_',' ').title())}</p></div>")
        except Exception:logger.exception("Unable to send admin payment email",extra={"company_id":company.id,"payment_id":entity_id})
    if config and config.whatsapp_enabled and member_mobile and installment_number is not None:
        amount_text=f"{amount:,.2f}"
        try:await send_whatsapp_template(config,recipient=member_mobile,template_name="collection_success_member",language_code="en",body_parameters=[member_name,str(installment_number),amount_text,scheme_name,receipt_number])
        except Exception:logger.exception("Unable to send member collection WhatsApp",extra={"company_id":company.id,"payment_id":entity_id})
        try:await send_whatsapp_template(config,recipient=company.mobile_number,template_name="collection_success_admin",language_code="en",body_parameters=[member_name,str(installment_number),amount_text,scheme_name,collector_name or "Owner/Admin",receipt_number])
        except Exception:logger.exception("Unable to send owner collection WhatsApp",extra={"company_id":company.id,"payment_id":entity_id})
async def meta_configuration_status(config:CommunicationSettings|None):
    return {"whatsapp_enabled":bool(config and config.whatsapp_enabled),"phone_number_id":config.whatsapp_phone_number_id if config else None,"business_account_id":config.whatsapp_business_account_id if config else None,"api_version":config.whatsapp_api_version if config else "v23.0","access_token_configured":bool(config and config.whatsapp_access_token_encrypted)}
async def send_whatsapp_template(config:CommunicationSettings,*,recipient:str,template_name:str,language_code:str="en",body_parameters:list[str]|None=None):
    if not config.whatsapp_enabled:raise RuntimeError("WhatsApp is not enabled")
    if not config.whatsapp_phone_number_id or not config.whatsapp_access_token_encrypted:raise RuntimeError("WhatsApp credentials are incomplete")
    template={"name":template_name,"language":{"code":language_code}}
    if body_parameters:template["components"]=[{"type":"body","parameters":[{"type":"text","text":str(value)} for value in body_parameters]}]
    payload={"messaging_product":"whatsapp","recipient_type":"individual","to":recipient.removeprefix("+"),"type":"template","template":template}
    url=f"https://graph.facebook.com/{config.whatsapp_api_version}/{config.whatsapp_phone_number_id}/messages"
    token=decrypt_secret(config.whatsapp_access_token_encrypted)
    async with httpx.AsyncClient(timeout=20) as client:
        response=await client.post(url,json=payload,headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"})
        response.raise_for_status()
        return response.json()
