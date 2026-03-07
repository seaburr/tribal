from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text

from .database import Base


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    dri = Column(String, nullable=False)
    expiration_date = Column(Date, nullable=False)
    purpose = Column(Text, nullable=False)
    generation_instructions = Column(Text, nullable=False)
    secret_manager_link = Column(String, nullable=True)
    slack_webhook = Column(String, nullable=False)
    type = Column(String, nullable=False, server_default="Other")
    public_key_pem = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ReminderLog(Base):
    __tablename__ = "reminder_logs"

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    expiration_date = Column(Date, nullable=False)
    days_before = Column(Integer, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
