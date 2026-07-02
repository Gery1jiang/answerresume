from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from services.database import Base


class Stats(Base):
    __tablename__ = "stats"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    event_type = Column(String)
    session_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
