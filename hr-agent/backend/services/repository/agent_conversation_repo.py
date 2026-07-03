from datetime import datetime
from services.models.agent_conversation import AgentConversation
from .base import BaseRepository


class AgentConversationRepository(BaseRepository[AgentConversation]):
    def get_model(self) -> type[AgentConversation]:
        return AgentConversation

    def list_by_session(self, session_id: str, user_id: str = "", limit: int = 20) -> list[AgentConversation]:
        q = self.db.query(AgentConversation).filter(
            AgentConversation.session_id == session_id
        )
        if user_id:
            q = q.filter(AgentConversation.user_id == user_id)
        return q.order_by(AgentConversation.created_at.asc()).limit(limit).all()

    def list_recent_by_session(self, session_id: str, user_id: str = "", max_turns: int = 10) -> list[AgentConversation]:
        limit = max_turns * 5
        q = self.db.query(AgentConversation).filter(
            AgentConversation.session_id == session_id
        )
        if user_id:
            q = q.filter(AgentConversation.user_id == user_id)
        records = q.order_by(AgentConversation.created_at.desc()).limit(limit).all()
        records.reverse()
        return records

    def clear_by_session(self, session_id: str, user_id: str = ""):
        q = self.db.query(AgentConversation).filter(
            AgentConversation.session_id == session_id
        )
        if user_id:
            q = q.filter(AgentConversation.user_id == user_id)
        q.delete()
        self.db.commit()

    def clear_all_by_user(self, user_id: str):
        self.db.query(AgentConversation).filter(
            AgentConversation.user_id == user_id
        ).delete()
        self.db.commit()

    def add_message(self, session_id: str, role: str, content: str, user_id: str = "", resume_id: int | None = None, guide_id: int | None = None):
        record = AgentConversation(
            session_id=session_id,
            role=role,
            content=content,
            user_id=user_id,
            resume_id=resume_id,
            guide_id=guide_id,
        )
        self.db.add(record)
        self.db.commit()
