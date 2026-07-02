from datetime import datetime
from services.models.agent_task import AgentTask
from .base import BaseRepository


class AgentTaskRepository(BaseRepository[AgentTask]):
    def get_model(self) -> type[AgentTask]:
        return AgentTask

    def get_latest(self, session_id: str, user_id: str = "") -> AgentTask | None:
        q = self.db.query(AgentTask).filter(
            AgentTask.session_id == session_id
        )
        if user_id:
            q = q.filter(AgentTask.user_id == user_id)
        return q.order_by(AgentTask.created_at.desc()).first()

    def cancel_pending(self, session_id: str, user_id: str):
        existing = self.db.query(AgentTask).filter(
            AgentTask.session_id == session_id,
            AgentTask.user_id == user_id,
            AgentTask.status.in_(["pending", "running"]),
        ).all()
        for t in existing:
            t.status = "cancelled"
            t.updated_at = datetime.utcnow()
        if existing:
            self.db.commit()

    def create_task(self, session_id: str, user_id: str, request: str, status: str = "pending") -> AgentTask:
        task = AgentTask(
            session_id=session_id,
            user_id=user_id,
            status=status,
            request=request,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def has_active(self, session_id: str, user_id: str) -> bool:
        return self.db.query(AgentTask).filter(
            AgentTask.session_id == session_id,
            AgentTask.user_id == user_id,
            AgentTask.status.in_(["pending", "running"]),
        ).count() > 0

    def delete_by_session(self, session_id: str, user_id: str = ""):
        q = self.db.query(AgentTask).filter(
            AgentTask.session_id == session_id,
        )
        if user_id:
            q = q.filter(AgentTask.user_id == user_id)
        q.delete()
        self.db.commit()
