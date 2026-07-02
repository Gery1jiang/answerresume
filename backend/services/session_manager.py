import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlalchemy.orm import Session as DBSession
from config import settings
from .database import SessionLocal
from .models import Session, Conversation

class SessionManager:
    MAX_CONVERSATION_TURNS = 3

    def __init__(self):
        self._memory_sessions: Dict[str, dict] = {}
        self._ip_fail_counts: Dict[str, dict] = {}

    def create_session(self, db: DBSession, user_id: str = "") -> str:
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        db_session = Session(
            id=session_id,
            user_id=user_id,
            created_at=now,
            last_active=now,
            is_active=True
        )
        db.add(db_session)
        db.commit()

        self._memory_sessions[session_id] = {
            "created_at": now,
            "last_active": now,
            "is_active": True,
            "user_id": user_id,
        }
        return session_id

    def get_session_user_id(self, session_id: str) -> str:
        """Get the user_id associated with a session."""
        if session_id in self._memory_sessions:
            return self._memory_sessions[session_id].get("user_id", "")
        db = SessionLocal()
        try:
            db_session = db.query(Session).filter(Session.id == session_id).first()
            if db_session:
                return db_session.user_id or ""
            return ""
        finally:
            db.close()

    def validate_session(self, session_id: str) -> bool:
        if session_id not in self._memory_sessions:
            db = SessionLocal()
            try:
                db_session = db.query(Session).filter(Session.id == session_id).first()
                if db_session and db_session.is_active:
                    now = datetime.utcnow()
                    timeout = timedelta(minutes=settings.SESSION_TIMEOUT_MINUTES)
                    if now - db_session.last_active <= timeout:
                        self._memory_sessions[session_id] = {
                            "created_at": db_session.created_at,
                            "last_active": db_session.last_active,
                            "is_active": db_session.is_active,
                            "user_id": db_session.user_id or "",
                        }
                        return True
                return False
            finally:
                db.close()
        session_data = self._memory_sessions[session_id]
        if not session_data.get("is_active"):
            return False
        timeout = timedelta(minutes=settings.SESSION_TIMEOUT_MINUTES)
        if datetime.utcnow() - session_data["last_active"] > timeout:
            self._memory_sessions[session_id]["is_active"] = False
            return False
        return True

    def refresh_session(self, session_id: str):
        if session_id in self._memory_sessions:
            self._memory_sessions[session_id]["last_active"] = datetime.utcnow()

    def cleanup_expired_sessions(self):
        timeout = timedelta(minutes=settings.SESSION_TIMEOUT_MINUTES)
        now = datetime.utcnow()
        expired_ids = []
        for session_id, data in self._memory_sessions.items():
            if now - data["last_active"] > timeout:
                data["is_active"] = False
                expired_ids.append(session_id)
        # 从内存中移除过期 session，防止泄漏撑爆内存
        for sid in expired_ids:
            del self._memory_sessions[sid]

    def get_active_count(self) -> int:
        # 先做一次轻量清理，防止测试 session 堆积撑满 max_sessions
        self.cleanup_expired_sessions()
        return sum(1 for s in self._memory_sessions.values() if s.get("is_active"))

    def get_conversation_history(self, db: DBSession, session_id: str) -> List[dict]:
        conversations = db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).order_by(Conversation.created_at.desc()).limit(self.MAX_CONVERSATION_TURNS * 2).all()
        
        history = []
        for c in reversed(conversations):
            history.append({"role": c.role, "content": c.content})
        
        return history[-self.MAX_CONVERSATION_TURNS*2:]

    def set_booking_suggestion(self, session_id: str, intent: str, booking_time: Optional[str] = None):
        if session_id in self._memory_sessions:
            if self._memory_sessions[session_id].get("booking_suggested"):
                return  # 同session只触发一次
            self._memory_sessions[session_id]["booking_suggested"] = True
            self._memory_sessions[session_id]["booking_intent"] = intent
            if booking_time:
                self._memory_sessions[session_id]["booking_time"] = booking_time

    def get_booking_suggestion(self, session_id: str) -> Optional[dict]:
        if session_id in self._memory_sessions:
            s = self._memory_sessions[session_id]
            if s.get("booking_suggested"):
                result = {"suggest_booking": True, "booking_intent": s.get("booking_intent", "interview_interest")}
                bt = s.get("booking_time")
                if bt:
                    result["booking_time"] = bt
                return result
        return None

    def clear_booking_suggestion(self, session_id: str):
        if session_id in self._memory_sessions:
            self._memory_sessions[session_id]["booking_suggested"] = False
            self._memory_sessions[session_id]["booking_intent"] = None
            self._memory_sessions[session_id].pop("booking_time", None)

    def build_context_from_history(self, history: List[dict]) -> str:
        if not history:
            return ""
        context_parts = []
        for msg in history:
            role = "用户" if msg["role"] == "user" else "AI"
            context_parts.append(f"{role}: {msg['content']}")
        return "\n\n".join(context_parts)

    def check_ip_locked(self, client_ip: str) -> bool:
        if client_ip not in self._ip_fail_counts:
            return False
        fail_data = self._ip_fail_counts[client_ip]
        if datetime.utcnow() - fail_data["first_fail"] > timedelta(minutes=10):
            del self._ip_fail_counts[client_ip]
            return False
        return fail_data["count"] >= 5

    def record_failed_attempt(self, client_ip: str):
        if client_ip not in self._ip_fail_counts:
            self._ip_fail_counts[client_ip] = {"count": 1, "first_fail": datetime.utcnow()}
        else:
            self._ip_fail_counts[client_ip]["count"] += 1

    def clear_failed_attempts(self, client_ip: str):
        if client_ip in self._ip_fail_counts:
            del self._ip_fail_counts[client_ip]

session_manager = SessionManager()
