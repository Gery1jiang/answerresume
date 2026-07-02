from services.models.system_config import SystemConfig
from .base import BaseRepository


class SystemConfigRepository(BaseRepository[SystemConfig]):
    def get_model(self) -> type[SystemConfig]:
        return SystemConfig

    def get_by_key(self, key: str) -> SystemConfig | None:
        return self.db.query(SystemConfig).filter(
            SystemConfig.key == key
        ).first()

    def get_value(self, key: str, default: str = "") -> str:
        cfg = self.get_by_key(key)
        return cfg.value if cfg else default
