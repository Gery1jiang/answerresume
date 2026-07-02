import json
from datetime import datetime
from services.models.agent_event import AgentEvent
from .base import BaseRepository


class AgentEventRepository(BaseRepository[AgentEvent]):
    def get_model(self) -> type[AgentEvent]:
        return AgentEvent

    def list_by_session(self, session_id: str) -> list[AgentEvent]:
        return self.db.query(AgentEvent).filter(
            AgentEvent.session_id == session_id
        ).order_by(AgentEvent.sequence).all()

    def delete_by_session_task(self, session_id: str, task_id: int):
        self.db.query(AgentEvent).filter(
            AgentEvent.session_id == session_id,
            AgentEvent.task_id == task_id,
        ).delete()
        self.db.commit()

    def delete_by_session(self, session_id: str, user_id: str = ""):
        q = self.db.query(AgentEvent).filter(
            AgentEvent.session_id == session_id
        )
        if user_id:
            q = q.filter(AgentEvent.user_id == user_id)
        q.delete()
        self.db.commit()

    def delete_before(self, before: datetime, user_id: str = ""):
        q = self.db.query(AgentEvent).filter(
            AgentEvent.created_at < before
        )
        if user_id:
            q = q.filter(AgentEvent.user_id == user_id)
        result = q.delete()
        self.db.commit()
        return result

    def add_event(self, session_id: str, task_id: int, event_type: str, event_data: dict, sequence: int, user_id: str = ""):
        record = AgentEvent(
            session_id=session_id,
            user_id=user_id,
            task_id=task_id,
            event_type=event_type,
            event_data=json.dumps(event_data, ensure_ascii=False),
            sequence=sequence,
        )
        self.db.add(record)
        self.db.commit()

    def get_latest_sequence(self, session_id: str) -> int:
        last = self.db.query(AgentEvent).filter(
            AgentEvent.session_id == session_id,
        ).order_by(AgentEvent.sequence.desc()).first()
        return (last.sequence + 1) if last else 0
