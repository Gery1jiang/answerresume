from sqlalchemy import Column, String, Text, DateTime
from datetime import datetime
from services.database import Base


class SystemConfig(Base):
    __tablename__ = "system_configs"
    key = Column(String, primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
