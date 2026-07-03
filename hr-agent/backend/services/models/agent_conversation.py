from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from services.database import Base


class AgentConversation(Base):
    __tablename__ = "agent_conversations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text)
    resume_id = Column(Integer, nullable=True)
    guide_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
