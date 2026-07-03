from services.models.prompt_template import PromptTemplate, PromptVersion
from .base import BaseRepository


class PromptTemplateRepository(BaseRepository[PromptTemplate]):
    def get_model(self) -> type[PromptTemplate]:
        return PromptTemplate

    def get_by_key(self, key: str) -> PromptTemplate | None:
        return self.db.query(PromptTemplate).filter(
            PromptTemplate.key == key
        ).first()
