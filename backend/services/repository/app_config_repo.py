import json
from datetime import datetime

from services.models.app_config import AppConfig


class AppConfigRepository:
    def __init__(self, db):
        self.db = db

    def get_data_dict(self, category: str) -> dict:
        row = self.db.query(AppConfig).filter(AppConfig.category == category).first()
        if row and row.data:
            return json.loads(row.data)
        return {}

    def upsert(self, category: str, data: str) -> AppConfig:
        row = self.db.query(AppConfig).filter(AppConfig.category == category).first()
        if row:
            row.data = data
            row.updated_at = datetime.utcnow()
        else:
            row = AppConfig(category=category, data=data)
            self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def merge_data(self, category: str, data: dict) -> dict:
        existing = self.get_data_dict(category)
        existing.update(data)
        self.upsert(category, json.dumps(existing, ensure_ascii=False))
        return existing
