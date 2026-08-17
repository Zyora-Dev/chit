from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class CommunicationSettings(Base):
    __tablename__="communication_settings";__table_args__=(UniqueConstraint("company_id",name="uq_communication_company"),)
    id:Mapped[int]=mapped_column(primary_key=True);company_id:Mapped[int]=mapped_column(ForeignKey("companies.id",ondelete="CASCADE"),index=True,nullable=False)
    admin_email:Mapped[str|None]=mapped_column(String(320));email_payment_notifications:Mapped[bool]=mapped_column(Boolean,default=True,server_default=text("true"),nullable=False)
    whatsapp_enabled:Mapped[bool]=mapped_column(Boolean,default=False,server_default=text("false"),nullable=False);whatsapp_phone_number_id:Mapped[str|None]=mapped_column(String(100));whatsapp_business_account_id:Mapped[str|None]=mapped_column(String(100));whatsapp_access_token_encrypted:Mapped[str|None]=mapped_column(Text)
    whatsapp_api_version:Mapped[str]=mapped_column(String(20),default="v23.0",server_default="v23.0",nullable=False);updated_by_user_id:Mapped[int|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False);updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)

class InAppNotification(Base):
    __tablename__="in_app_notifications"
    id:Mapped[int]=mapped_column(primary_key=True);company_id:Mapped[int]=mapped_column(ForeignKey("companies.id",ondelete="CASCADE"),index=True,nullable=False);user_id:Mapped[int|None]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    notification_type:Mapped[str]=mapped_column(String(50),index=True,nullable=False);title:Mapped[str]=mapped_column(String(250),nullable=False);message:Mapped[str]=mapped_column(String(1000),nullable=False);href:Mapped[str|None]=mapped_column(String(500));entity_type:Mapped[str|None]=mapped_column(String(80));entity_id:Mapped[int|None]=mapped_column(Integer);read_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),index=True,nullable=False)
