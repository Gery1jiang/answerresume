from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from datetime import datetime
from services.database import Base


class ApplicantProfile(Base):
    __tablename__ = "applicant_profile"
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    home_address = Column(String, default="")
    home_lng = Column(Float, nullable=True)
    home_lat = Column(Float, nullable=True)
    default_travel_mode = Column(String, default="transit")
    interview_duration_min = Column(Integer, default=60)
    min_gap_min = Column(Integer, default=120)
    max_daily_interviews = Column(Integer, default=3)
    workday_start = Column(String, default="09:00")
    workday_end = Column(String, default="18:00")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
