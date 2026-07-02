from services.models.resume import Resume
from .base import BaseRepository


class ResumeRepository(BaseRepository[Resume]):
    def get_model(self) -> type[Resume]:
        return Resume

    def list_by_user(self, user_id: str, limit: int = 50) -> list[Resume]:
        return self.db.query(Resume).filter(
            Resume.user_id == user_id
        ).order_by(Resume.created_at.desc()).limit(limit).all()

    def count_by_user(self, user_id: str) -> int:
        return self.db.query(Resume).filter(Resume.user_id == user_id).count()

    def get_default(self, user_id: str) -> Resume | None:
        return self.db.query(Resume).filter(
            Resume.user_id == user_id, Resume.is_default.is_(True)
        ).first()

    def search(self, user_id: str, keyword: str = "", limit: int = 200) -> list[Resume]:
        q = self.db.query(Resume).filter(Resume.user_id == user_id)
        if keyword:
            q = q.filter(Resume.title.contains(keyword) | Resume.filename.contains(keyword))
        return q.order_by(Resume.created_at.desc()).limit(min(limit, 200)).all()
