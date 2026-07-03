from sqlalchemy import Column, Integer, String, Text, Float, DateTime
from datetime import datetime
from services.database import Base


class InterviewGuide(Base):
    __tablename__ = "interview_guides"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    company_name = Column(String, nullable=False)
    company_description = Column(Text, default="")
    job_title = Column(String, nullable=False)
    hr_name = Column(String, default="")
    hr_phone = Column(String, default="")
    hr_email = Column(String, default="")
    interview_address = Column(String, nullable=False)
    interview_address_lng = Column(Float, nullable=True)
    interview_address_lat = Column(Float, nullable=True)
    address_type = Column(String, default="offline")
    video_link = Column(String, default="")
    salary = Column(String, default="")
    interview_round = Column(String, default="")
    interview_time = Column(DateTime, nullable=False)
    result = Column(String, default="")
    status = Column(String, default="pending")
    commute_duration_min = Column(Integer, nullable=True)
    commute_distance_km = Column(Float, nullable=True)
    conflict_warnings = Column(Text, default="[]")
    guide_content = Column(Text, default="{}")
    generated_report_id = Column(Integer, nullable=True)
    jd_text = Column(Text, default="")
    jd_parsed = Column(Text, default="{}")
    generated_report_md = Column(Text, default="")
    source = Column(String, default="manual")
    session_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
