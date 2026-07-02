from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from services.database import Base


class AgentEvent(Base):
    __tablename__ = "agent_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False, index=True)
    user_id = Column(String, default="", index=True)
    task_id = Column(Integer, nullable=False)
    event_type = Column(String, nullable=False)
    event_data = Column(Text, nullable=True)
    sequence = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
