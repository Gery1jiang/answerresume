from datetime import datetime
from services.models.session import Session
from .base import BaseRepository


class SessionRepository(BaseRepository[Session]):
    def get_model(self) -> type[Session]:
        return Session

    def list_active(self, user_id: str) -> list[Session]:
        return self.db.query(Session).filter(
            Session.user_id == user_id,
            Session.is_active.is_(True),
        ).all()

    def count_active(self, user_id: str) -> int:
        return self.db.query(Session).filter(
            Session.user_id == user_id,
            Session.is_active.is_(True),
        ).count()

    def list_all(self) -> list[Session]:
        return self.db.query(Session).order_by(Session.created_at.desc()).all()

    def delete_by_user(self, user_id: str) -> int:
        return self.db.query(Session).filter(Session.user_id == user_id).delete()

    def delete_all(self) -> int:
        return self.db.query(Session).delete()

    def expire_old(self, minutes: int = 120):
        cutoff = datetime.utcnow().timestamp() - minutes * 60
        self.db.query(Session).filter(
            Session.last_active < datetime.fromtimestamp(cutoff),
            Session.is_active.is_(True),
        ).update({"is_active": False})
        self.db.commit()
