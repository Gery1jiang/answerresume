import uuid
from sqlalchemy import Column, String, Boolean, DateTime
from datetime import datetime
from services.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, nullable=False, index=True)  # login ID, alphanumeric
    display_name = Column(String, default="")  # display name (can be Chinese)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")  # super_admin | user
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
