from services.models.interview_guide import InterviewGuide
from .base import BaseRepository


class InterviewGuideRepository(BaseRepository[InterviewGuide]):
    def get_model(self) -> type[InterviewGuide]:
        return InterviewGuide

    def search(self, user_id: str, company: str = "", job_title: str = "") -> InterviewGuide | None:
        q = self.db.query(InterviewGuide).filter(InterviewGuide.user_id == user_id)
        if company:
            q = q.filter(InterviewGuide.company_name.ilike(f"%{company}%"))
        if job_title:
            q = q.filter(InterviewGuide.job_title.ilike(f"%{job_title}%"))
        return q.order_by(InterviewGuide.created_at.desc()).first()

    def list_by_user(self, user_id: str, keyword: str = "", status: str = "", limit: int = 200) -> list[InterviewGuide]:
        q = self.db.query(InterviewGuide).filter(InterviewGuide.user_id == user_id)
        if keyword:
            q = q.filter(
                InterviewGuide.company_name.contains(keyword)
                | InterviewGuide.job_title.contains(keyword)
            )
        if status:
            q = q.filter(InterviewGuide.status == status)
        return q.order_by(InterviewGuide.created_at.desc()).limit(min(limit, 200)).all()

    def count_unique_companies(self, user_id: str) -> int:
        return self.db.query(InterviewGuide.company_name).filter(
            InterviewGuide.user_id == user_id
        ).distinct().count()

    def get_by_session_id(self, session_id: str) -> InterviewGuide | None:
        return self.db.query(InterviewGuide).filter(
            InterviewGuide.session_id == session_id
        ).order_by(InterviewGuide.created_at.desc()).first()
