from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime
from services.database import Base


class ReportGenerationTask(Base):
    __tablename__ = "report_generation_tasks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    guide_id = Column(Integer, ForeignKey("interview_guides.id"), nullable=False)
    status = Column(String, default="pending")
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    pdf_path = Column(String, nullable=True)
    progress_message = Column(String, default="")
