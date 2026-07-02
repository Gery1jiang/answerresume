from sqlalchemy.orm import Session
from services.database import SessionLocal

from .user_repo import UserRepository
from .crawled_job_repo import CrawledJobRepository
from .resume_repo import ResumeRepository
from .interview_guide_repo import InterviewGuideRepository
from .knowledge_base_repo import KnowledgeBaseRepository
from .agent_conversation_repo import AgentConversationRepository
from .agent_task_repo import AgentTaskRepository
from .agent_event_repo import AgentEventRepository
from .session_repo import SessionRepository
from .conversation_repo import ConversationRepository
from .stats_repo import StatsRepository
from .applicant_profile_repo import ApplicantProfileRepository
from .user_config_repo import UserConfigRepository
from .system_config_repo import SystemConfigRepository
from .portfolio_config_repo import PortfolioConfigRepository
from .portfolio_content_repo import PortfolioContentRepository
from .prompt_template_repo import PromptTemplateRepository
from .report_generation_task_repo import ReportGenerationTaskRepository
from .llm_usage_repo import LLMUsageRepository
from .app_config_repo import AppConfigRepository


class RepoContainer:
    """Repository 容器：每个请求创建一个，确保所有 Repo 共享同一个 DB session。"""

    def __init__(self, db: Session | None = None):
        self._db = db or SessionLocal()
        self._own_db = db is None

    def close(self):
        if self._own_db and self._db:
            self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ── repositories ────────────────────────────────────

    @property
    def user(self) -> UserRepository:
        return UserRepository(self._db)

    @property
    def crawled_job(self) -> CrawledJobRepository:
        return CrawledJobRepository(self._db)

    @property
    def resume(self) -> ResumeRepository:
        return ResumeRepository(self._db)

    @property
    def interview_guide(self) -> InterviewGuideRepository:
        return InterviewGuideRepository(self._db)

    @property
    def knowledge_base(self) -> KnowledgeBaseRepository:
        return KnowledgeBaseRepository(self._db)

    @property
    def agent_conversation(self) -> AgentConversationRepository:
        return AgentConversationRepository(self._db)

    @property
    def agent_task(self) -> AgentTaskRepository:
        return AgentTaskRepository(self._db)

    @property
    def agent_event(self) -> AgentEventRepository:
        return AgentEventRepository(self._db)

    @property
    def session(self) -> SessionRepository:
        return SessionRepository(self._db)

    @property
    def conversation(self) -> ConversationRepository:
        return ConversationRepository(self._db)

    @property
    def stats(self) -> StatsRepository:
        return StatsRepository(self._db)

    @property
    def applicant_profile(self) -> ApplicantProfileRepository:
        return ApplicantProfileRepository(self._db)

    @property
    def user_config(self) -> UserConfigRepository:
        return UserConfigRepository(self._db)

    @property
    def system_config(self) -> SystemConfigRepository:
        return SystemConfigRepository(self._db)

    @property
    def portfolio_config(self) -> PortfolioConfigRepository:
        return PortfolioConfigRepository(self._db)

    @property
    def portfolio_content(self) -> PortfolioContentRepository:
        return PortfolioContentRepository(self._db)

    @property
    def prompt_template(self) -> PromptTemplateRepository:
        return PromptTemplateRepository(self._db)

    @property
    def report_task(self) -> ReportGenerationTaskRepository:
        return ReportGenerationTaskRepository(self._db)

    @property
    def llm_usage(self) -> LLMUsageRepository:
        return LLMUsageRepository(self._db)

    @property
    def app_config(self) -> AppConfigRepository:
        return AppConfigRepository(self._db)
