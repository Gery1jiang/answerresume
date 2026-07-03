from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, UniqueConstraint
from datetime import datetime
from services.database import Base


class Resume(Base):
    __tablename__ = "resumes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    filename = Column(String, nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_default = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("user_id", "filename", name="uq_user_resume_filename"),
    )
