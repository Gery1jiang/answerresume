from services.models.conversation import Conversation
from .base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    def get_model(self) -> type[Conversation]:
        return Conversation

    def list_by_session(self, session_id: str) -> list[Conversation]:
        return self.db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).order_by(Conversation.created_at.asc()).all()

    def count_by_user(self, user_id: str, since=None) -> int:
        q = self.db.query(Conversation).filter(Conversation.user_id == user_id)
        if since:
            q = q.filter(Conversation.created_at >= since)
        return q.count()

    def count_by_question(self, user_id: str | None = None, limit: int = 20) -> list[tuple[str, int]]:
        from sqlalchemy import func
        q = self.db.query(
            Conversation.content,
            func.count(Conversation.id).label("count"),
        ).filter(Conversation.role == "user")
        if user_id:
            q = q.filter(Conversation.user_id == user_id)
        return q.group_by(Conversation.content).order_by(
            func.count(Conversation.id).desc()
        ).limit(limit).all()

    def delete_by_user(self, user_id: str) -> int:
        return self.db.query(Conversation).filter(Conversation.user_id == user_id).delete()

    def delete_all(self) -> int:
        return self.db.query(Conversation).delete()
