from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from services.database import Base


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    key = Column(String(128), primary_key=True)
    description = Column(Text, default="")
    content = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    created_by = Column(String(64), default="system")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    prompt_key = Column(String(128), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    change_log = Column(Text, default="")
    created_by = Column(String(64), default="system")
    created_at = Column(DateTime, default=datetime.utcnow)
