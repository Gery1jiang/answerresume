from sqlalchemy import Column, Integer, String, DateTime, Index
from datetime import datetime
from services.database import Base


class LLMUsage(Base):
    __tablename__ = "llm_usage"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)
    model = Column(String, default="")
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    search_calls = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_llm_usage_user_date", "user_id", "created_at"),
    )
