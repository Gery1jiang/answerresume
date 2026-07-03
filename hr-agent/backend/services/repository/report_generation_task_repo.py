from services.models.report_generation_task import ReportGenerationTask
from .base import BaseRepository


class ReportGenerationTaskRepository(BaseRepository[ReportGenerationTask]):
    def get_model(self) -> type[ReportGenerationTask]:
        return ReportGenerationTask
