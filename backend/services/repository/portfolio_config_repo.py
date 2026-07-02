from services.models.portfolio_config import PortfolioConfig
from .base import BaseRepository


class PortfolioConfigRepository(BaseRepository[PortfolioConfig]):
    def get_model(self) -> type[PortfolioConfig]:
        return PortfolioConfig

    def get_by_user(self, user_id: str) -> PortfolioConfig | None:
        return self.db.query(PortfolioConfig).filter(
            PortfolioConfig.user_id == user_id
        ).first()

    def upsert(self, user_id: str, **data) -> PortfolioConfig:
        cfg = self.get_by_user(user_id)
        if cfg:
            for k, v in data.items():
                if v is not None and hasattr(cfg, k):
                    setattr(cfg, k, v)
            self.db.commit()
            self.db.refresh(cfg)
            return cfg
        return self.create(user_id=user_id, **data)
