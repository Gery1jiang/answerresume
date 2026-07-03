from services.models.user_config import UserConfig
from .base import BaseRepository


class UserConfigRepository(BaseRepository[UserConfig]):
    def get_model(self) -> type[UserConfig]:
        return UserConfig

    def get_by_user(self, user_id: str) -> UserConfig | None:
        return self.db.query(UserConfig).filter(
            UserConfig.user_id == user_id
        ).first()

    def get_by_key(self, user_id: str, config_key: str) -> UserConfig | None:
        return self.db.query(UserConfig).filter(
            UserConfig.user_id == user_id,
            UserConfig.config_key == config_key,
        ).first()

    def upsert(self, user_id: str, config_key: str, config_value: str) -> UserConfig:
        existing = self.get_by_key(user_id, config_key)
        if existing:
            existing.config_value = config_value
            self.db.commit()
            self.db.refresh(existing)
            return existing
        return self.create(user_id=user_id, config_key=config_key, config_value=config_value)
