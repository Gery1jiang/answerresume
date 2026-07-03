import json

from services.models.knowledge_base import KnowledgeBase
from .base import BaseRepository


class KnowledgeBaseRepository(BaseRepository[KnowledgeBase]):
    def get_model(self) -> type[KnowledgeBase]:
        return KnowledgeBase

    def get_by_category(self, user_id: str, category: str) -> KnowledgeBase | None:
        return self.db.query(KnowledgeBase).filter(
            KnowledgeBase.user_id == user_id,
            KnowledgeBase.category == category,
        ).first()

    def list_by_user(self, user_id: str, keyword: str = "", limit: int = 200) -> list[KnowledgeBase]:
        q = self.db.query(KnowledgeBase).filter(KnowledgeBase.user_id == user_id)
        if keyword:
            q = q.filter(
                KnowledgeBase.category.contains(keyword)
                | KnowledgeBase.data.contains(keyword)
            )
        return q.order_by(KnowledgeBase.updated_at.desc()).limit(limit).all()

    def upsert(self, user_id: str, category: str, data: str) -> KnowledgeBase:
        existing = self.get_by_category(user_id, category)
        if existing:
            existing.data = data
            self.db.commit()
            self.db.refresh(existing)
            return existing
        return self.create(user_id=user_id, category=category, data=data)

    def get_data_dict(self, user_id: str, category: str) -> dict:
        """Load config as dict from KnowledgeBase KV store."""
        row = self.get_by_category(user_id, category)
        if row and row.data:
            return json.loads(row.data)
        return {}

    def merge_data(self, user_id: str, category: str, data: dict) -> dict:
        """Merge data dict into existing KV entry. Returns the merged dict."""
        existing_data = self.get_data_dict(user_id, category)
        existing_data.update(data)
        self.upsert(user_id, category, json.dumps(existing_data, ensure_ascii=False))
        return existing_data
