from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from services.database import Base


class AppConfig(Base):
    __tablename__ = "app_configs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(100), unique=True, nullable=False, comment="配置分类")
    data = Column(Text, nullable=True, comment="JSON 配置数据")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
