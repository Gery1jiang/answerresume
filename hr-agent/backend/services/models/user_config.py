from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from datetime import datetime
from services.database import Base


class UserConfig(Base):
    __tablename__ = "user_configs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    config_key = Column(String, nullable=False)
    config_value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "config_key", name="uq_user_config"),
    )
