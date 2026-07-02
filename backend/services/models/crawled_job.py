from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from services.database import Base


class CrawledJob(Base):
    __tablename__ = "crawled_jobs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    platform = Column(String, default="manual")
    title = Column(String, default="")
    company = Column(String, default="")
    city = Column(String, default="")
    salary = Column(String, default="")
    jd_text = Column(Text, default="")
    jd_url = Column(String, default="")
    jd_parsed = Column(Text, default="")
    work_address = Column(String, default="")
    match_score = Column(Integer, nullable=True)
    match_detail = Column(Text, default="")
    status = Column(String, default="matched")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
