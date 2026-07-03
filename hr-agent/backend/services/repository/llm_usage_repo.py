from services.models.llm_usage import LLMUsage
from .base import BaseRepository


class LLMUsageRepository(BaseRepository[LLMUsage]):
    def get_model(self) -> type[LLMUsage]:
        return LLMUsage

    def record(self, user_id: str, input_tokens: int, output_tokens: int) -> LLMUsage:
        return self.create(
            user_id=user_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def sum_by_user(self, user_id: str) -> dict:
        from sqlalchemy import func
        row = self.db.query(
            func.coalesce(func.sum(LLMUsage.input_tokens), 0),
            func.coalesce(func.sum(LLMUsage.output_tokens), 0),
        ).filter(LLMUsage.user_id == user_id).first()
        return {"input_tokens": row[0], "output_tokens": row[1]} if row else {"input_tokens": 0, "output_tokens": 0}
