from services.models.crawled_job import CrawledJob
from .base import BaseRepository


class CrawledJobRepository(BaseRepository[CrawledJob]):
    def get_model(self) -> type[CrawledJob]:
        return CrawledJob

    def search(self, user_id: str, keywords: str = "", city: str = "") -> list[CrawledJob]:
        q = self.db.query(CrawledJob).filter(CrawledJob.user_id == user_id)
        if keywords:
            keyword = keywords.split()[0]
            q = q.filter(
                CrawledJob.title.contains(keywords)
                | CrawledJob.company.contains(keywords)
                | CrawledJob.jd_text.contains(keyword)
            )
        if city:
            q = q.filter(CrawledJob.city.contains(city))
        return q.order_by(CrawledJob.created_at.desc()).all()

    def find_duplicate(self, jd_url: str, title: str, company: str, user_id: str) -> CrawledJob | None:
        return self.db.query(CrawledJob).filter(
            CrawledJob.jd_url == jd_url,
            CrawledJob.title == title,
            CrawledJob.company == company,
            CrawledJob.user_id == user_id,
        ).first()

    def list_recent(self, user_id: str, limit: int = 20) -> list[CrawledJob]:
        return self.db.query(CrawledJob).filter(
            CrawledJob.user_id == user_id
        ).order_by(CrawledJob.created_at.desc()).limit(limit).all()

    def search_by_user(self, user_id: str, keyword: str = "", status: str = "", limit: int = 200) -> list[CrawledJob]:
        q = self.db.query(CrawledJob).filter(CrawledJob.user_id == user_id)
        if keyword:
            q = q.filter(CrawledJob.title.contains(keyword) | CrawledJob.company.contains(keyword))
        if status:
            q = q.filter(CrawledJob.status == status)
        return q.order_by(CrawledJob.created_at.desc()).limit(min(limit, 200)).all()
