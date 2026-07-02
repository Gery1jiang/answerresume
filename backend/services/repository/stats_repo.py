from datetime import datetime
from services.models.stats import Stats
from .base import BaseRepository


class StatsRepository(BaseRepository[Stats]):
    def get_model(self) -> type[Stats]:
        return Stats

    def count_events(self, user_id: str, event_type: str, since: datetime | None = None) -> int:
        q = self.db.query(Stats).filter(
            Stats.user_id == user_id,
            Stats.event_type == event_type,
        )
        if since:
            q = q.filter(Stats.created_at >= since)
        return q.count()

    def record_event(self, user_id: str, event_type: str, session_id: str = ""):
        stat = Stats(user_id=user_id, event_type=event_type, session_id=session_id)
        self.db.add(stat)
        self.db.commit()

    def delete_by_user(self, user_id: str) -> int:
        return self.db.query(Stats).filter(Stats.user_id == user_id).delete()

    def delete_all(self) -> int:
        return self.db.query(Stats).delete()
