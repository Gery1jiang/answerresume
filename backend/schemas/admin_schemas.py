from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


# ── Applicant Profile ──────────────────────────────────────────────

class ApplicantProfileResponse(BaseModel):
    home_address: str = ""
    home_lng: Optional[float] = None
    home_lat: Optional[float] = None
    default_travel_mode: str = "transit"
    interview_duration_min: int = 60
    min_gap_min: int = 120
    max_daily_interviews: int = 3
    workday_start: str = "09:00"
    workday_end: str = "18:00"


class ApplicantProfileUpdate(BaseModel):
    home_address: Optional[str] = None
    home_lng: Optional[float] = None
    home_lat: Optional[float] = None
    default_travel_mode: Optional[str] = None
    interview_duration_min: Optional[int] = None
    min_gap_min: Optional[int] = None
    max_daily_interviews: Optional[int] = None
    workday_start: Optional[str] = None
    workday_end: Optional[str] = None


class ApplicantProfileUpdateResponse(BaseModel):
    message: str
    profile: ApplicantProfileResponse


# ── Interview Guide ────────────────────────────────────────────────

class InterviewGuideCreate(BaseModel):
    company_name: str = Field(..., min_length=1)
    job_title: str = Field(..., min_length=1)
    interview_time: str
    company_description: Optional[str] = ""
    hr_name: Optional[str] = ""
    hr_phone: Optional[str] = ""
    hr_email: Optional[str] = ""
    interview_address: str = ""
    interview_address_lng: Optional[float] = None
    interview_address_lat: Optional[float] = None
    address_type: Optional[str] = "offline"
    video_link: Optional[str] = ""
    salary: Optional[str] = ""
    interview_round: Optional[str] = ""
    jd_text: Optional[str] = ""
    result: Optional[str] = ""
    source: Optional[str] = "manual"
    session_id: Optional[str] = None


class InterviewGuideUpdate(BaseModel):
    company_name: Optional[str] = None
    company_description: Optional[str] = None
    job_title: Optional[str] = None
    hr_name: Optional[str] = None
    hr_phone: Optional[str] = None
    hr_email: Optional[str] = None
    interview_address: Optional[str] = None
    interview_address_lng: Optional[float] = None
    interview_address_lat: Optional[float] = None
    address_type: Optional[str] = None
    video_link: Optional[str] = None
    salary: Optional[str] = None
    interview_round: Optional[str] = None
    interview_time: Optional[str] = None
    status: Optional[str] = None
    result: Optional[str] = None
    jd_text: Optional[str] = None
    jd_parsed: Optional[str] = None


class InterviewGuideResponse(BaseModel):
    id: int
    company_name: str
    company_description: str
    job_title: str
    salary: str = ""
    hr_name: str
    hr_phone: str
    hr_email: str
    interview_address: str
    interview_address_lng: Optional[float] = None
    interview_address_lat: Optional[float] = None
    address_type: str = "offline"
    video_link: str = ""
    interview_round: str = ""
    interview_time: Optional[str] = None
    status: str
    result: str = ""
    commute_duration_min: Optional[int] = None
    commute_distance_km: Optional[float] = None
    conflict_warnings: list[Any] = []
    guide_content: dict[str, Any] = {}
    generated_report_id: Optional[int] = None
    jd_text: str = ""
    jd_parsed: dict[str, Any] = {}
    generated_report_md: str = ""
    source: str = "manual"
    session_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class InterviewGuideListResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list[InterviewGuideResponse]


class InterviewGuideDeleteResponse(BaseModel):
    message: str


# ── Stats ──────────────────────────────────────────────────────────

class StatsResponse(BaseModel):
    total_sessions: int = 0
    total_conversations: int = 0
    total_chat_questions: int = 0
    total_resume_downloads: int = 0
    total_portfolio_visits: int = 0
    daily_new_users: int = 0
    conversations_today: int = 0
    total_knowledge_entries: int = 0
    today_new_knowledge: int = 0
    top_questions: list[Any] = []


class QuestionStatsItem(BaseModel):
    question: str
    count: int


class QuestionStatsResponse(BaseModel):
    items: list[QuestionStatsItem] = []


class QuestionAddRequest(BaseModel):
    question: str = Field(..., min_length=1)


class QuestionAddResponse(BaseModel):
    message: str


class StatsClearResponse(BaseModel):
    message: str


# ── Generic ─────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str


class IdResponse(BaseModel):
    id: int


# ── Report Generation ──────────────────────────────────────────────

class GenerateReportResponse(BaseModel):
    task_id: int
    status: str


class TaskStatusResponse(BaseModel):
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    pdf_path: Optional[str] = None


class JdParseResponse(BaseModel):
    summary: str = ""
    requirements: list[Any] = []
    responsibilities: list[Any] = []
    keywords: list[str] = []


# ── Knowledge Base ─────────────────────────────────────────────────

class KnowledgeEntry(BaseModel):
    id: int
    category: str
    key: str
    value: str
    updated_at: Optional[str] = None


class KnowledgeCategoryResponse(BaseModel):
    category: str
    content: str = ""


# ── Resume ─────────────────────────────────────────────────────────

class ResumeListItem(BaseModel):
    id: int
    title: str = ""
    job_title: str = ""
    is_default: bool = False
    created_at: Optional[str] = None


class ResumeListResponse(BaseModel):
    resumes: list[ResumeListItem] = []


class ResumeDetailResponse(BaseModel):
    id: int
    title: str = ""
    content: str = ""
    created_at: Optional[str] = None
    is_default: bool = False


class ResumeTemplateResponse(BaseModel):
    message: str
    template: str


# ── Toggles ────────────────────────────────────────────────────────

class ToggleResponse(BaseModel):
    enabled: bool


# ── Sessions ───────────────────────────────────────────────────────

class SessionSummary(BaseModel):
    id: str
    created_at: Optional[str] = None
    last_active: Optional[str] = None
    is_active: bool = True


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary] = []


class ConversationMessage(BaseModel):
    role: str
    content: str
    created_at: Optional[str] = None


class ConversationListResponse(BaseModel):
    conversations: list[ConversationMessage] = []


# ── Request Models (replace req: dict) ──────────────────────────────

class TestLLMRequest(BaseModel):
    provider: str = ""
    model: str = ""
    api_key: str = ""
    base_url: str = ""

class TestEmbeddingRequest(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = ""

class GenerateResumeWithTemplateRequest(BaseModel):
    raw_text: str = ""
    target_job: str
    template: str = "modern"
    user_id: str = ""

class UpdateResumeTemplateRequest(BaseModel):
    template: str

class KnowledgePreviewRequest(BaseModel):
    category: str = ""
    content: str = ""
    action: str = ""

class KnowledgeConfirmRequest(BaseModel):
    preview_id: str = ""

class AddAppendixPathRequest(BaseModel):
    path: str = ""

class RemoveAppendixDirRequest(BaseModel):
    path: str = ""

class ListDirectoriesRequest(BaseModel):
    path: str = ""

class CrawlJobsRequest(BaseModel):
    keywords: str = ""
    city: str = ""
    platform: str = "51job"
    max_count: int = 5
    sort: str = "time"
    threshold: int = 0
    auto_match: bool = True

class CrawlJobItem(BaseModel):
    platform: str = "boss"
    title: str = ""
    company: str = ""
    city: str = ""
    salary: str = ""
    jd_text: str = ""
    jd_url: str = ""
    work_address: str = ""

class CrawlSubmitRequest(BaseModel):
    jobs: list[CrawlJobItem] = []

class BatchDeleteJobsRequest(BaseModel):
    ids: list[int] = []


# ── Additional Response Models ─────────────────────────────────────

class TemplatesResponse(BaseModel):
    templates: list[str] = []


class ResumeGenerateResponse(BaseModel):
    message: str
    resume_id: int


class ResumeStatusResponse(BaseModel):
    resume_show: bool


class PortfolioStatusResponse(BaseModel):
    portfolio_show: bool
    chat_enabled: bool = False


class ResumePreviewResponse(BaseModel):
    html: str = ""
    css: str = ""
    content: str = ""


class DirectoriesResponse(BaseModel):
    entries: list[dict] = []
    parent: str = ""
    error: str = ""


class JobListItem(BaseModel):
    id: int
    platform: str = ""
    title: str = ""
    company: str = ""
    city: str = ""
    salary: str = ""
    jd_url: str = ""
    work_address: str = ""
    match_score: Optional[int] = None
    match_detail: Optional[dict] = None
    status: str = ""
    created_at: Optional[str] = None


class JobListResponse(BaseModel):
    jobs: list[JobListItem] = []


class JobDetailResponse(BaseModel):
    id: int
    platform: str = ""
    title: str = ""
    company: str = ""
    city: str = ""
    salary: str = ""
    jd_text: str = ""
    jd_url: str = ""
    jd_parsed: Optional[dict] = None
    work_address: str = ""
    match_score: Optional[int] = None
    match_detail: Optional[dict] = None
    status: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class JobAddResponse(BaseModel):
    message: str
    id: int


class JobMatchResponse(BaseModel):
    message: str
    score: int
    detail: dict = {}


class JobBatchMatchResponse(BaseModel):
    message: str
    results: list[dict] = []


class JobBatchMatchRequest(BaseModel):
    ids: list[int] = []


class CrawlJobsResponse(BaseModel):
    message: str
    count: int = 0
    jobs: list[dict] = []
    skipped_dedup: int = 0
    skipped_expired: int = 0
    skipped_score: int = 0


class CrawlSubmitResponse(BaseModel):
    message: str
    count: int = 0


class UploadResponse(BaseModel):
    url: str


class KnowledgeStructuredResponse(BaseModel):
    category: str
    data: dict = {}


class KnowledgePreviewResponse(BaseModel):
    success: bool = True
    message: str = ""
    category: str = ""
    changes: list[dict] = []


class KnowledgeConfirmResponse(BaseModel):
    success: bool = True
    message: str = ""


class AppendixDirsResponse(BaseModel):
    dirs: list[str] = []


class AppendixInfoResponse(BaseModel):
    configured_dirs: list[str] = []
    doc_count: int = 0
    chunk_count: int = 0


class AppendixUploadResponse(BaseModel):
    message: str
    count: int = 0
    files: int = 0


class AppendixRecordsResponse(BaseModel):
    records: list[dict] = []


class GenerateIntroResponse(BaseModel):
    self_intro: str = ""
    initial_message: str = ""


class ResumeViewDataResponse(BaseModel):
    id: int
    filename: str = ""
    title: str = ""
    content: str = ""
    created_at: Optional[str] = None
    is_default: bool = False


class ResumeToggleResponse(BaseModel):
    message: str
    resume_show: bool


class PortfolioToggleResponse(BaseModel):
    message: str
    portfolio_show: bool
