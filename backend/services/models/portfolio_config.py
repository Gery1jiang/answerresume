from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey
from datetime import datetime
from services.database import Base


class PortfolioConfig(Base):
    __tablename__ = "portfolio_configs"
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    style = Column(String, default="editorial")
    blocks_order = Column(Text, default='["hero", "about", "experience", "projects", "contact"]')
    blocks_hidden = Column(Text, default='[]')
    contact_enabled = Column(Text, default='{"email": true, "phone": true, "github": true, "wechat": false}')
    chat_enabled = Column(Boolean, default=False)
    chat_position = Column(String, default="bottom-right")
    portfolio_show = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
