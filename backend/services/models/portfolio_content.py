from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from datetime import datetime
from services.database import Base


class PortfolioContent(Base):
    __tablename__ = "portfolio_contents"
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    content_json = Column(Text, default="{}")
    built_at = Column(DateTime, default=datetime.utcnow)
