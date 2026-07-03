from services.models.portfolio_content import PortfolioContent
from .base import BaseRepository


class PortfolioContentRepository(BaseRepository[PortfolioContent]):
    def get_model(self) -> type[PortfolioContent]:
        return PortfolioContent

    def get_by_user(self, user_id: str) -> PortfolioContent | None:
        return self.db.query(PortfolioContent).filter(
            PortfolioContent.user_id == user_id
        ).first()

    def upsert(self, user_id: str, **data) -> PortfolioContent:
        content = self.get_by_user(user_id)
        if content:
            for k, v in data.items():
                if v is not None and hasattr(content, k):
                    setattr(content, k, v)
            self.db.commit()
            self.db.refresh(content)
            return content
        return self.create(user_id=user_id, **data)
