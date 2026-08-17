from pydantic import BaseModel,EmailStr,Field
class CommunicationSettingsUpdate(BaseModel):
    admin_email:EmailStr|None=None;email_payment_notifications:bool=True;whatsapp_enabled:bool=False;whatsapp_phone_number_id:str|None=Field(default=None,max_length=100);whatsapp_business_account_id:str|None=Field(default=None,max_length=100);whatsapp_access_token:str|None=Field(default=None,max_length=2000);whatsapp_api_version:str=Field(default="v23.0",pattern=r"^v\d+\.\d+$")
class NotificationRead(BaseModel):notification_ids:list[int]=Field(default_factory=list,max_length=100)
class WhatsAppTemplateTest(BaseModel):
    recipient:str=Field(pattern=r"^\+[1-9]\d{7,14}$")
    template_name:str=Field(min_length=1,max_length=512,pattern=r"^[a-z0-9_]+$")
    language_code:str=Field(default="en",min_length=2,max_length=10,pattern=r"^[A-Za-z_-]+$")
