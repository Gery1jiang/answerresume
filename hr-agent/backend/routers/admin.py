from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse, HTMLResponse
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta, timezone
import json
import jwt
import os
import tempfile
import shutil
import uuid, asyncio
from config import settings
from services.database import get_db
from services.models import User, KnowledgeBase, InterviewGuide, ReportGenerationTask, Resume, CrawledJob, UserConfig
from services.rag_service import rag_service
from services.prompt_manager import prompt_manager
from services.enums import EventType
from services.resume_service import resume_service
from services.pdf_service import _generate_pdf_async
from services.applicant_profile_service import applicant_profile_service
from services.portfolio_service import portfolio_service
from services.interview_guide_service import interview_guide_service
from services.report_generator import generate_full_report
from routers.deps import get_current_user, require_super_admin
from schemas.admin_schemas import (
    ApplicantProfileResponse, ApplicantProfileUpdate, ApplicantProfileUpdateResponse,
    InterviewGuideCreate, InterviewGuideUpdate, InterviewGuideResponse,
    InterviewGuideListResponse, InterviewGuideDeleteResponse,
    MessageResponse, GenerateReportResponse, TaskStatusResponse, JdParseResponse,
    KnowledgeEntry, KnowledgeCategoryResponse,
    ResumeListItem, ResumeListResponse, ResumeDetailResponse,
    ToggleResponse, SessionListResponse, ConversationListResponse,
    TestLLMRequest, TestEmbeddingRequest,
    GenerateResumeWithTemplateRequest, UpdateResumeTemplateRequest,
    KnowledgePreviewRequest, KnowledgeConfirmRequest,
    AddAppendixPathRequest, RemoveAppendixDirRequest,
    ListDirectoriesRequest, CrawlJobsRequest, CrawlSubmitRequest,
    BatchDeleteJobsRequest,
    TemplatesResponse, ResumeGenerateResponse, ResumeStatusResponse,
    PortfolioStatusResponse, ResumePreviewResponse, DirectoriesResponse,
    JobListResponse, JobDetailResponse, JobAddResponse, JobMatchResponse,
    JobBatchMatchResponse, JobBatchMatchRequest, CrawlJobsResponse, CrawlSubmitResponse,
    UploadResponse, KnowledgeStructuredResponse, KnowledgePreviewResponse,
    KnowledgeConfirmResponse, AppendixDirsResponse, AppendixInfoResponse,
    AppendixUploadResponse, AppendixRecordsResponse, GenerateIntroResponse,
    ResumeViewDataResponse, ResumeToggleResponse, PortfolioToggleResponse,
)

class StatsSessionItem(BaseModel):
    session_id: str
    created_at: Optional[str] = None
    conversation_count: int = 0
    download_count: int = 0


class StatsSummaryResponse(BaseModel):
    visit_count: int = 0
    chat_count: int = 0
    download_count: int = 0
    portfolio_count: int = 0
    sessions: list[StatsSessionItem] = []


class QuestionStatsItem(BaseModel):
    question: str
    count: int


class QuestionStatsResponse(BaseModel):
    questions: list[QuestionStatsItem] = []


class QuestionAddRequest(BaseModel):
    question: str


class QuestionAddResponse(BaseModel):
    message: str = ""


class StatsClearResponse(BaseModel):
    message: str = ""


router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBearer()

def format_beijing_time(dt):
    if not dt:
        return None
    beijing_tz = timezone(timedelta(hours=8))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")

def create_token(username: str, role: str = "super_admin", user_id: str = "") -> str:
    payload = {"sub": username, "role": role, "user_id": user_id, "exp": datetime.utcnow() + timedelta(hours=24)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=["HS256"])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token 已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的 Token")

def get_token_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """从 JWT 提取 user_id，兜底用 username 查 DB。"""
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id", "")
        if user_id and str(user_id).strip():
            return user_id
        username = payload.get("sub", "")
        if username:
            from services.models import User
            from services.database import SessionLocal
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.username == username).first()
                if user:
                    return user.id
            finally:
                db.close()
        return ""
    except Exception:
        return ""


def get_token_role(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """从 JWT 提取角色。"""
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=["HS256"])
        return payload.get("role", "user")
    except Exception:
        return "user"


class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str = "super_admin"
    user_id: str = ""
    username: str = ""
    display_name: str = ""

class ConfigResponse(BaseModel):
    max_sessions: int
    session_timeout_minutes: int
    resume_show: bool
    portfolio_show: bool = False
    visitor_password: str
    llm_provider: str
    llm_model: str
    llm_api_key: str
    embedding_provider: str
    embedding_model: str
    embedding_api_key: str
    appendix_knowledge_dir: str = ""
    visitor_llm_provider: str = "DeepSeek"
    visitor_llm_model: str = "deepseek-v4-flash"
    visitor_llm_api_key: str = ""
    tavily_api_key: str = ""
    firecrawl_api_key: str = ""
    anysearch_api_key: str = ""
    amap_api_key: str = ""
    visitor_tavily_api_key: str = ""
    visitor_amap_api_key: str = ""
    intent_llm_provider: str = ""
    intent_llm_model: str = ""
    intent_llm_api_key: str = ""

class ConfigUpdateRequest(BaseModel):
    max_sessions: Optional[int] = None
    session_timeout_minutes: Optional[int] = None
    resume_show: Optional[bool] = None
    portfolio_show: Optional[bool] = None
    visitor_password: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_api_key: Optional[str] = None
    appendix_knowledge_dir: Optional[str] = None
    visitor_llm_provider: Optional[str] = None
    visitor_llm_model: Optional[str] = None
    visitor_llm_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None
    firecrawl_api_key: Optional[str] = None
    anysearch_api_key: Optional[str] = None
    amap_api_key: Optional[str] = None
    visitor_tavily_api_key: Optional[str] = None
    visitor_amap_api_key: Optional[str] = None
    intent_llm_provider: Optional[str] = None
    intent_llm_model: Optional[str] = None
    intent_llm_api_key: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class MyConfigResponse(BaseModel):
    visitor_enabled: bool = False
    visitor_password: str = ""

class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None

class MyConfigUpdateRequest(BaseModel):
    visitor_enabled: Optional[bool] = None
    visitor_password: Optional[str] = None

@router.get("/my-config", response_model=MyConfigResponse)
async def get_my_config(current_user: User = Depends(get_current_user)):
    from services.repository.container import RepoContainer
    from services.database import SessionLocal
    db = SessionLocal()
    try:
        repo = RepoContainer(db)
        enabled_cfg = repo.user_config.get_by_key(current_user.id, "visitor_enabled")
        pwd_cfg = repo.user_config.get_by_key(current_user.id, "visitor_password")
        return MyConfigResponse(
            visitor_enabled=enabled_cfg.config_value == "true" if enabled_cfg else False,
            visitor_password=pwd_cfg.config_value if pwd_cfg else "",
        )
    finally:
        db.close()

@router.post("/my-config", response_model=MessageResponse)
async def update_my_config(req: MyConfigUpdateRequest, current_user: User = Depends(get_current_user)):
    from services.repository.container import RepoContainer
    from services.database import SessionLocal
    db = SessionLocal()
    try:
        repo = RepoContainer(db)
        if req.visitor_enabled is not None:
            repo.user_config.upsert(current_user.id, "visitor_enabled", "true" if req.visitor_enabled else "false")
        if req.visitor_password is not None:
            if req.visitor_password and len(req.visitor_password) < 4:
                raise HTTPException(status_code=400, detail="口令至少4位")
            repo.user_config.upsert(current_user.id, "visitor_password", req.visitor_password or "")
        return {"message": "配置已保存"}
    finally:
        db.close()

class KnowledgeDataRequest(BaseModel):
    data: dict

class KnowledgeSaveRequest(BaseModel):
    content: str

class ResumeGenerateRequest(BaseModel):
    raw_text: str = ""
    target_job: str
    user_id: str = ""

class PromptRequest(BaseModel):
    content: str

class PromptResponse(BaseModel):
    content: str

@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    from services.database import SessionLocal
    from services.models import User
    from routers.auth import _check_password
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == req.username).first()
        if not user or not _check_password(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        if user.is_active is False:
            raise HTTPException(status_code=403, detail="账号已禁用")
        token = create_token(user.username, user.role, user.id)
        return LoginResponse(access_token=token, role=user.role, user_id=user.id, username=user.username, display_name=user.display_name or user.username)
    finally:
        db.close()

@router.post("/change-password", response_model=MessageResponse)
async def change_password(req: ChangePasswordRequest, current_user: User = Depends(require_super_admin)):
    if req.old_password != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="旧密码错误")
    
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码长度至少为6位")
    
    settings.ADMIN_PASSWORD = req.new_password
    return {"message": "密码修改成功"}

@router.get("/me")
async def get_my_profile(current_user: User = Depends(get_current_user)):
    return {"display_name": current_user.display_name or "", "email": current_user.email}


@router.post("/update-profile", response_model=MessageResponse)
async def update_my_profile(req: UpdateProfileRequest, current_user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    from services.repository.container import RepoContainer
    user = RepoContainer(db).user.get_by_id(current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    data = {}
    if req.display_name is not None:
        data["display_name"] = req.display_name
    if req.email is not None:
        data["email"] = req.email
    if data:
        RepoContainer(db).user.update(current_user.id, **data)
    return {"message": "个人信息已更新"}


@router.get("/resume/templates", response_model=TemplatesResponse)
async def get_resume_templates(current_user: User = Depends(get_current_user)):
    from services.resume_templates import list_templates
    return {"templates": [t["key"] for t in list_templates()]}

@router.get("/config", response_model=ConfigResponse)
async def get_config(current_user: User = Depends(require_super_admin)):
    portfolio_cfg = portfolio_service.get_config()
    db_cfg = _load_config("app_config")
    return ConfigResponse(
        max_sessions=db_cfg.get("max_sessions", settings.MAX_SESSIONS),
        session_timeout_minutes=db_cfg.get("session_timeout_minutes", settings.SESSION_TIMEOUT_MINUTES),
        resume_show=db_cfg.get("resume_show", settings.RESUME_SHOW),
        portfolio_show=portfolio_cfg.get("portfolio_show", False),
        visitor_password=db_cfg.get("visitor_password", settings.VISITOR_PASSWORD),
        llm_provider=db_cfg.get("llm_provider", settings.ADMIN_LLM_PROVIDER),
        llm_model=db_cfg.get("llm_model", settings.ADMIN_LLM_MODEL),
        llm_api_key=db_cfg.get("llm_api_key", settings.ADMIN_API_KEY),
        embedding_provider=db_cfg.get("embedding_provider", "SiliconFlow"),
        embedding_model=db_cfg.get("embedding_model", settings.SILICONFLOW_EMBEDDING_MODEL),
        embedding_api_key=db_cfg.get("embedding_api_key", settings.SILICONFLOW_API_KEY),
        appendix_knowledge_dir=db_cfg.get("appendix_knowledge_dir", ""),
        visitor_llm_provider=db_cfg.get("visitor_llm_provider", "DeepSeek"),
        visitor_llm_model=db_cfg.get("visitor_llm_model", "deepseek-v4-flash"),
        visitor_llm_api_key=db_cfg.get("visitor_llm_api_key", settings.VISITOR_API_KEY),
        tavily_api_key=db_cfg.get("tavily_api_key", settings.TAVILY_API_KEY),
        firecrawl_api_key=db_cfg.get("firecrawl_api_key", settings.FIRECRAWL_API_KEY),
        anysearch_api_key=db_cfg.get("anysearch_api_key", settings.ANYSEARCH_API_KEY),
        amap_api_key=db_cfg.get("amap_api_key", settings.AMAP_API_KEY),
        visitor_tavily_api_key=db_cfg.get("visitor_tavily_api_key", settings.VISITOR_TAVILY_API_KEY),
        visitor_amap_api_key=db_cfg.get("visitor_amap_api_key", settings.VISITOR_AMAP_API_KEY),
        intent_llm_provider=db_cfg.get("intent_llm_provider", ""),
        intent_llm_model=db_cfg.get("intent_llm_model", ""),
        intent_llm_api_key=db_cfg.get("intent_llm_api_key", ""),
    )

@router.post("/config", response_model=MessageResponse)
async def update_config(req: ConfigUpdateRequest, current_user: User = Depends(require_super_admin)):
    provider_base_urls = {
        "SiliconFlow": "https://api.siliconflow.cn/v1",
        "LongCat": "https://api.longcat.chat/openai/v1",
        "阿里云": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "百度智能云": "https://qianfan.baidubce.com/v2",
        "字节云": "https://ark.cn-beijing.volces.com/api/v3",
        "腾讯云": "https://hunyuan.tencentcs.com/v2",
        "智谱AI": "https://open.bigmodel.cn/api/paas/v4",
        "百川智能": "https://api.baichuan-ai.com/v1",
        "DeepSeek": "https://api.deepseek.com/v1",
        "月之暗面": "https://api.moonshot.cn/v1",
        "OpenAI": "https://api.openai.com/v1",
        "Anthropic": "https://api.anthropic.com/v1",
        "Google": "https://generativelanguage.googleapis.com/v1beta"
    }

    # Collect all changes to persist
    app_updates = {}

    if req.max_sessions is not None:
        settings.MAX_SESSIONS = req.max_sessions
        app_updates["max_sessions"] = req.max_sessions
    if req.session_timeout_minutes is not None:
        settings.SESSION_TIMEOUT_MINUTES = req.session_timeout_minutes
        app_updates["session_timeout_minutes"] = req.session_timeout_minutes
    if req.llm_model is not None:
        settings.ADMIN_LLM_MODEL = req.llm_model
        app_updates["llm_model"] = req.llm_model
    if req.llm_api_key is not None:
        settings.ADMIN_API_KEY = req.llm_api_key
        app_updates["llm_api_key"] = req.llm_api_key
    if req.llm_provider is not None:
        settings.ADMIN_LLM_PROVIDER = req.llm_provider
        app_updates["llm_provider"] = req.llm_provider
    if req.embedding_model is not None:
        settings.SILICONFLOW_EMBEDDING_MODEL = req.embedding_model
        app_updates["embedding_model"] = req.embedding_model
    if req.embedding_api_key is not None:
        settings.SILICONFLOW_API_KEY = req.embedding_api_key
        app_updates["embedding_api_key"] = req.embedding_api_key
    if req.resume_show is not None:
        settings.RESUME_SHOW = req.resume_show
        app_updates["resume_show"] = req.resume_show
    if req.portfolio_show is not None:
        portfolio_service.save_config({"portfolio_show": req.portfolio_show})
    if req.visitor_password is not None:
        if len(req.visitor_password) < 4:
            raise HTTPException(status_code=400, detail="访客口令长度至少为4位")
        settings.VISITOR_PASSWORD = req.visitor_password
        app_updates["visitor_password"] = req.visitor_password
    if req.appendix_knowledge_dir is not None:
        settings.APPENDIX_KNOWLEDGE_DIR = req.appendix_knowledge_dir
        app_updates["appendix_knowledge_dir"] = req.appendix_knowledge_dir
    if req.visitor_llm_provider is not None:
        settings.VISITOR_LLM_PROVIDER = req.visitor_llm_provider
        app_updates["visitor_llm_provider"] = req.visitor_llm_provider
    if req.visitor_llm_api_key is not None:
        settings.VISITOR_API_KEY = req.visitor_llm_api_key
        app_updates["visitor_llm_api_key"] = req.visitor_llm_api_key
    if req.visitor_llm_model is not None:
        settings.VISITOR_LLM_MODEL = req.visitor_llm_model
        app_updates["visitor_llm_model"] = req.visitor_llm_model
    if req.tavily_api_key is not None:
        settings.TAVILY_API_KEY = req.tavily_api_key
        app_updates["tavily_api_key"] = req.tavily_api_key
    if req.firecrawl_api_key is not None:
        settings.FIRECRAWL_API_KEY = req.firecrawl_api_key
        app_updates["firecrawl_api_key"] = req.firecrawl_api_key
    if req.anysearch_api_key is not None:
        settings.ANYSEARCH_API_KEY = req.anysearch_api_key
        app_updates["anysearch_api_key"] = req.anysearch_api_key
    if req.amap_api_key is not None:
        settings.AMAP_API_KEY = req.amap_api_key
        app_updates["amap_api_key"] = req.amap_api_key
    if req.visitor_tavily_api_key is not None:
        settings.VISITOR_TAVILY_API_KEY = req.visitor_tavily_api_key
        app_updates["visitor_tavily_api_key"] = req.visitor_tavily_api_key
    if req.visitor_amap_api_key is not None:
        settings.VISITOR_AMAP_API_KEY = req.visitor_amap_api_key
        app_updates["visitor_amap_api_key"] = req.visitor_amap_api_key
    if req.intent_llm_provider is not None:
        app_updates["intent_llm_provider"] = req.intent_llm_provider
    if req.intent_llm_model is not None:
        app_updates["intent_llm_model"] = req.intent_llm_model
    if req.intent_llm_api_key is not None:
        app_updates["intent_llm_api_key"] = req.intent_llm_api_key

    if app_updates:
        _save_config("app_config", app_updates)
        # 同步写入 app_configs 表（运行时 LLM 配置读取的来源）
        _save_app_config(app_updates)
    return {"message": "配置已更新"}

@router.post("/config/test-llm", response_model=MessageResponse)
async def test_llm_connection(req: TestLLMRequest, current_user: User = Depends(require_super_admin)):
    from openai import OpenAI
    provider = req.provider
    model = req.model
    api_key = req.api_key
    base_url = req.base_url

    if not all([provider, model, api_key, base_url]):
        raise HTTPException(status_code=400, detail="缺少必要参数")

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=10
        )
        if response and response.choices:
            return {"message": "连接成功"}
        raise HTTPException(status_code=400, detail="模型返回为空")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"连接失败: {str(e)}")

@router.post("/config/test-embedding", response_model=MessageResponse)
async def test_embedding_connection(req: TestEmbeddingRequest, current_user: User = Depends(require_super_admin)):
    api_key = req.api_key
    base_url = req.base_url
    model = req.model
    if not all([api_key, base_url, model]):
        raise HTTPException(status_code=400, detail="缺少必要参数")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        client.embeddings.create(model=model, input="test", encoding_format="float")
        return {"message": "连接成功"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"连接失败: {str(e)}")

@router.get("/applicant-profile", response_model=ApplicantProfileResponse)
async def get_applicant_profile(uid: str = Depends(get_token_user_id), db: DBSession = Depends(get_db)):
    profile = applicant_profile_service.get(db, user_id=uid)
    return ApplicantProfileResponse(
        home_address=profile.home_address,
        home_lng=profile.home_lng,
        home_lat=profile.home_lat,
        default_travel_mode=profile.default_travel_mode,
        interview_duration_min=profile.interview_duration_min,
        min_gap_min=profile.min_gap_min,
        max_daily_interviews=profile.max_daily_interviews,
        workday_start=profile.workday_start,
        workday_end=profile.workday_end,
    )


@router.put("/applicant-profile", response_model=ApplicantProfileUpdateResponse)
async def update_applicant_profile(data: ApplicantProfileUpdate, uid: str = Depends(get_token_user_id), db: DBSession = Depends(get_db)):
    profile = applicant_profile_service.update(db, data.model_dump(exclude_unset=True), user_id=uid)
    return ApplicantProfileUpdateResponse(message="更新成功", profile=ApplicantProfileResponse(
        home_address=profile.home_address,
        home_lng=profile.home_lng,
        home_lat=profile.home_lat,
        default_travel_mode=profile.default_travel_mode,
        interview_duration_min=profile.interview_duration_min,
        min_gap_min=profile.min_gap_min,
        max_daily_interviews=profile.max_daily_interviews,
        workday_start=profile.workday_start,
        workday_end=profile.workday_end,
    ))

@router.get("/interview-guide/list", response_model=InterviewGuideListResponse)
async def list_interview_guides(
    page: int = 1,
    size: int = 20,
    company: str = "",
    status: str = "",
    uid: str = Depends(get_token_user_id),
    db: DBSession = Depends(get_db),
):
    return interview_guide_service.list(db, page, size, company, status, user_id=uid)


@router.get("/interview-guide/{guide_id}", response_model=InterviewGuideResponse)
async def get_interview_guide(
    guide_id: int,
    uid: str = Depends(get_token_user_id),
    db: DBSession = Depends(get_db),
):
    result = interview_guide_service.get(db, guide_id, user_id=uid)
    if not result:
        raise HTTPException(status_code=404, detail="面试记录不存在")
    return result


@router.post("/interview-guide/create", response_model=InterviewGuideResponse)
async def create_interview_guide(
    data: InterviewGuideCreate,
    uid: str = Depends(get_token_user_id),
    db: DBSession = Depends(get_db),
):
    return interview_guide_service.create(db, data.model_dump(), user_id=uid)


@router.put("/interview-guide/{guide_id}", response_model=InterviewGuideResponse)
async def update_interview_guide(
    guide_id: int,
    data: InterviewGuideUpdate,
    uid: str = Depends(get_token_user_id),
    db: DBSession = Depends(get_db),
):
    result = interview_guide_service.update(db, guide_id, data.model_dump(exclude_unset=True), user_id=uid)
    if not result:
        raise HTTPException(status_code=404, detail="面试记录不存在")
    return result


@router.delete("/interview-guide/{guide_id}", response_model=InterviewGuideDeleteResponse)
async def delete_interview_guide(
    guide_id: int,
    uid: str = Depends(get_token_user_id),
    db: DBSession = Depends(get_db),
):
    success = interview_guide_service.delete(db, guide_id, user_id=uid)
    if not success:
        raise HTTPException(status_code=404, detail="面试记录不存在")
    return {"message": "删除成功"}


@router.put("/interview-guide/{guide_id}/status", response_model=MessageResponse)
async def update_interview_guide_status(
    guide_id: int,
    data: dict,
    uid: str = Depends(get_token_user_id),
    role: str = Depends(get_token_role),
    db: DBSession = Depends(get_db),
):
    valid_statuses = {"pending", "confirmed", "cancelled", "completed"}
    new_status = data.get("status", "")
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"无效状态: {new_status}")
    u = uid if role != "super_admin" else None
    result = interview_guide_service.update(db, guide_id, {"status": new_status}, user_id=u)
    if not result:
        raise HTTPException(status_code=404, detail="面试记录不存在")
    return {"message": "状态已更新"}


@router.post("/interview-guide/{guide_id}/generate-report", response_model=GenerateReportResponse)
async def trigger_report_generation(
    guide_id: int,
    background_tasks: BackgroundTasks,
    uid: str = Depends(get_token_user_id),
    role: str = Depends(get_token_role),
    db: DBSession = Depends(get_db),
):
    guide = db.query(InterviewGuide).filter(InterviewGuide.id == guide_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="面试记录不存在")
    if role != "super_admin" and guide.user_id != uid:
        raise HTTPException(status_code=403, detail="无权操作")
    asyncio.create_task(generate_full_report(guide_id))
    task = db.query(ReportGenerationTask).filter(ReportGenerationTask.guide_id == guide_id).first()
    if not task:
        task = ReportGenerationTask(guide_id=guide_id, user_id=guide.user_id, status="pending")
        db.add(task)
        db.commit()
        db.refresh(task)
    else:
        task.status = "pending"
        task.completed_at = None
        task.error_message = None
        task.pdf_path = None
        db.commit()
    return {"task_id": task.id, "status": task.status}


@router.post("/interview-guide/{guide_id}/cancel-report", response_model=MessageResponse)
async def cancel_report_generation(
    guide_id: int,
    uid: str = Depends(get_token_user_id),
    role: str = Depends(get_token_role),
    db: DBSession = Depends(get_db),
):
    guide = db.query(InterviewGuide).filter(InterviewGuide.id == guide_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="面试记录不存在")
    if role != "super_admin" and guide.user_id != uid:
        raise HTTPException(status_code=403, detail="无权操作")
    task = db.query(ReportGenerationTask).filter(
        ReportGenerationTask.guide_id == guide_id,
        ReportGenerationTask.status == "running",
    ).first()
    if task:
        task.status = "cancelled"
        task.completed_at = datetime.utcnow()
        task.error_message = "用户取消"
        db.commit()
    return {"message": "已取消报告生成"}


@router.get("/interview-guide/{guide_id}/task-status", response_model=TaskStatusResponse)
async def get_report_task_status(
    guide_id: int,
    uid: str = Depends(get_token_user_id),
    role: str = Depends(get_token_role),
    db: DBSession = Depends(get_db),
):
    guide = db.query(InterviewGuide).filter(InterviewGuide.id == guide_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="面试记录不存在")
    if role != "super_admin" and guide.user_id != uid:
        raise HTTPException(status_code=403, detail="无权访问")
    task = db.query(ReportGenerationTask).filter(
        ReportGenerationTask.guide_id == guide_id,
    ).order_by(ReportGenerationTask.completed_at.desc().nullslast()).first()
    if not task:
        return {"status": "none"}
    return {
        "status": task.status,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "error_message": task.error_message,
        "pdf_path": task.pdf_path,
    }


@router.get("/interview-guide/{guide_id}/report")
async def download_report(
    guide_id: int,
    uid: str = Depends(get_token_user_id),
    role: str = Depends(get_token_role),
    db: DBSession = Depends(get_db),
):
    from fastapi.responses import FileResponse
    from urllib.parse import quote

    guide = db.query(InterviewGuide).filter(InterviewGuide.id == guide_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="面试记录不存在")
    if role != "super_admin" and guide.user_id != uid:
        raise HTTPException(status_code=403, detail="无权访问")
    task = db.query(ReportGenerationTask).filter(
        ReportGenerationTask.guide_id == guide_id,
    ).order_by(ReportGenerationTask.completed_at.desc().nullslast()).first()
    if not task or not task.pdf_path or not os.path.exists(task.pdf_path):
        raise HTTPException(status_code=404, detail="报告未生成")
    filename = f"面试宝典_{guide.company_name}_{guide.job_title}.pdf"
    return FileResponse(
        task.pdf_path,
        media_type="application/pdf",
        filename=quote(filename),
    )


@router.get("/interview-guide/{guide_id}/report-preview")
async def preview_report(
    guide_id: int,
    uid: str = Depends(get_token_user_id),
    role: str = Depends(get_token_role),
    db: DBSession = Depends(get_db),
):
    guide = db.query(InterviewGuide).filter(InterviewGuide.id == guide_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="面试记录不存在")
    if role != "super_admin" and guide.user_id and guide.user_id != uid:
        raise HTTPException(status_code=403, detail="无权访问")
    if not guide.generated_report_md:
        raise HTTPException(status_code=404, detail="报告未生成")

    import markdown
    html_body = markdown.markdown(
        guide.generated_report_md,
        extensions=["tables", "fenced_code", "nl2br"],
    )
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: "PingFang SC", "Microsoft YaHei", "SimHei", sans-serif;
    background: #fff; color: #1a1a2e; line-height: 1.8;
    max-width: 900px; margin: 0 auto; padding: 40px 32px;
}}
h1 {{ font-size: 26px; color: #1a1a2e; border-bottom: 3px solid #0f3460; padding-bottom: 12px; margin: 32px 0 16px; }}
h2 {{ font-size: 20px; color: #0f3460; margin: 28px 0 12px; padding-left: 10px; border-left: 4px solid #0f3460; }}
h3 {{ font-size: 17px; color: #16213e; margin: 20px 0 10px; }}
p {{ margin: 8px 0; }}
table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 14px; }}
th, td {{ border: 1px solid #d0d5dd; padding: 8px 12px; text-align: left; }}
th {{ background: #f0f4f8; font-weight: 600; color: #1a1a2e; }}
tr:nth-child(even) td {{ background: #f8fafc; }}
blockquote {{
    border-left: 4px solid #0f3460; margin: 16px 0; padding: 12px 20px;
    background: #f0f4f8; color: #34495e; font-size: 14px;
}}
code {{ background: #f0f4f8; padding: 2px 6px; border-radius: 3px; font-size: 13px; }}
pre {{
    background: #1a1a2e; color: #e8e8e8; padding: 16px; border-radius: 6px;
    overflow-x: auto; font-size: 13px; line-height: 1.6; margin: 12px 0;
}}
ul, ol {{ margin: 8px 0; padding-left: 24px; }}
hr {{ border: none; border-top: 1px solid #e0e0e0; margin: 32px 0; }}
strong {{ color: #0f3460; }}
a {{ color: #0f3460; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
@media print {{
    body {{ padding: 0; }}
    h1, h2 {{ page-break-after: avoid; }}
}}
</style>
</head>
<body>
{html_body}
</body>
</html>"""
    return HTMLResponse(content=html)


@router.post("/interview-guide/parse-jd", response_model=JdParseResponse)
async def parse_jd(
    data: dict,
    uid: str = Depends(get_token_user_id),
):
    jd_text = data.get("jd_text", "")
    if not jd_text.strip():
        raise HTTPException(status_code=400, detail="JD 内容为空")
    from services.report_generator import _parse_jd
    result = await _parse_jd(jd_text)
    return result


@router.get("/interview-guide/{guide_id}/report-md")
async def download_report_md(
    guide_id: int,
    uid: str = Depends(get_token_user_id),
    role: str = Depends(get_token_role),
    db: DBSession = Depends(get_db),
):
    from fastapi.responses import PlainTextResponse
    from urllib.parse import quote

    guide = db.query(InterviewGuide).filter(InterviewGuide.id == guide_id).first()
    if not guide:
        raise HTTPException(status_code=404, detail="面试记录不存在")
    if role != "super_admin" and guide.user_id != uid:
        raise HTTPException(status_code=403, detail="无权访问")
    if not guide.generated_report_md:
        raise HTTPException(status_code=404, detail="Markdown 报告未生成")
    filename = f"面试宝典_{guide.company_name}_{guide.job_title}.md"
    return PlainTextResponse(
        content=guide.generated_report_md,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"
        },
    )


@router.get("/knowledge/{category}", response_model=KnowledgeCategoryResponse)
async def get_knowledge(category: str, uid: str = Depends(get_token_user_id)):
    from config import get_user_knowledge_dir
    knowledge_dir = get_user_knowledge_dir(uid)
    filepath = os.path.join(knowledge_dir, f"{category}.md")
    if not os.path.exists(filepath):
        # Fallback: read from DB KnowledgeBase table
        from services.database import SessionLocal
        from services.repository.container import RepoContainer
        db = SessionLocal()
        try:
            kb = RepoContainer(db).knowledge_base.get_by_category(uid, category)
            if kb and kb.data:
                # Re-sync to ensure file exists next time
                _sync_knowledge_to_md(category, json.loads(kb.data), uid)
                return {"category": category, "content": _generate_md_content(category, json.loads(kb.data))}
        finally:
            db.close()
        raise HTTPException(status_code=404, detail="知识库文件不存在")
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    return {"category": category, "content": content}

@router.post("/knowledge/{category}", response_model=MessageResponse)
async def save_knowledge(category: str, req: KnowledgeSaveRequest, uid: str = Depends(get_token_user_id)):
    from config import get_user_knowledge_dir
    knowledge_dir = get_user_knowledge_dir(uid)
    os.makedirs(knowledge_dir, exist_ok=True)
    filepath = os.path.join(knowledge_dir, f"{category}.md")
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(req.content)
        
        documents = rag_service.load_knowledge()
        rag_service.build_vector_store(documents)
        rag_service.init_qa_chain()
        
        return {"message": "知识库已更新，向量库已同步"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")

@router.post("/resume/generate", response_model=ResumeGenerateResponse)
async def generate_resume(req: ResumeGenerateRequest, uid: str = Depends(get_token_user_id)):
    try:
        if not req.target_job:
            raise HTTPException(status_code=400, detail="目标岗位不能为空")
        resume_id = resume_service.save_resume(req.raw_text, req.target_job, uid)
        return {"message": "简历生成成功", "resume_id": resume_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")

@router.post("/resume/generate-with-template", response_model=ResumeGenerateResponse)
async def generate_resume_with_template(req: GenerateResumeWithTemplateRequest, uid: str = Depends(get_token_user_id)):
    try:
        if not req.target_job:
            raise HTTPException(status_code=400, detail="目标岗位不能为空")
        resume_id = resume_service.save_resume(req.raw_text, req.target_job, uid)
        # Store the template key in resume content
        template = req.template
        from services.resume_service import resume_service as rs
        resume = rs.get_resume_by_id(resume_id)
        if resume and resume.content:
            import json
            data = json.loads(resume.content)
            data["_template"] = template
            resume.content = json.dumps(data, ensure_ascii=False)
            rs.db.commit()
        return {"message": "简历生成成功", "resume_id": resume_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")

@router.get("/resumes/{resume_id}", response_model=ResumeDetailResponse)
async def get_resume(resume_id: int, uid: str = Depends(get_token_user_id), role: str = Depends(get_token_role), db: DBSession = Depends(get_db)):
    try:
        resume = resume_service.get_resume_by_id(resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="简历不存在")
        if role != "super_admin" and resume.user_id != uid:
            raise HTTPException(status_code=403, detail="无权访问该简历")
        return {
            "id": resume.id,
            "title": resume.title,
            "content": resume.content,
            "created_at": format_beijing_time(resume.created_at),
            "is_default": resume.is_default
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")

@router.post("/resumes/{resume_id}/template", response_model=MessageResponse)
async def update_resume_template(resume_id: int, req: UpdateResumeTemplateRequest, uid: str = Depends(get_token_user_id), role: str = Depends(get_token_role)):
    try:
        import json
        resume = resume_service.get_resume_by_id(resume_id, user_id=uid if role != "super_admin" else "")
        if not resume:
            raise HTTPException(status_code=404, detail="简历不存在")
        if role != "super_admin" and resume.user_id != uid:
            raise HTTPException(status_code=403, detail="无权访问该简历")
        tmpl = req.template
        content = json.loads(resume.content)
        content["_template"] = tmpl
        resume.content = json.dumps(content, ensure_ascii=False)
        resume_service.db.commit()
        return {"message": "模板已更新", "template": tmpl}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.post("/resumes/{resume_id}/set-default", response_model=MessageResponse)
async def set_default_resume(resume_id: int, uid: str = Depends(get_token_user_id), role: str = Depends(get_token_role)):
    try:
        success = resume_service.set_default_resume(resume_id, user_id=uid if role != "super_admin" else "")
        if not success:
            raise HTTPException(status_code=404, detail="简历不存在")
        return {"message": "设置成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置失败: {str(e)}")

@router.delete("/resumes/{resume_id}", response_model=MessageResponse)
async def delete_resume(resume_id: int, uid: str = Depends(get_token_user_id), role: str = Depends(get_token_role)):
    try:
        success = resume_service.delete_resume(resume_id, user_id=uid if role != "super_admin" else "")
        if not success:
            raise HTTPException(status_code=404, detail="简历不存在")
        return {"message": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

@router.get("/resume/toggle", response_model=ResumeToggleResponse)
async def toggle_resume(uid: str = Depends(get_token_user_id)):
    from services.repository.container import RepoContainer
    from services.database import SessionLocal
    db = SessionLocal()
    try:
        repo = RepoContainer(db)
        cfg = repo.user_config.get_by_key(uid, "resume_show")
        current = cfg.config_value == "true" if cfg else False
        new_val = "false" if current else "true"
        repo.user_config.upsert(uid, "resume_show", new_val)
        return {"message": f"简历展示已{'开启' if new_val == 'true' else '关闭'}", "resume_show": new_val == "true"}
    finally:
        db.close()

@router.get("/resume/status", response_model=ResumeStatusResponse)
async def get_resume_status(uid: str = Depends(get_token_user_id)):
    from services.repository.container import RepoContainer
    from services.database import SessionLocal
    db = SessionLocal()
    try:
        cfg = RepoContainer(db).user_config.get_by_key(uid, "resume_show")
        return {"resume_show": cfg.config_value == "true" if cfg else False}
    finally:
        db.close()

@router.get("/portfolio/toggle", response_model=PortfolioToggleResponse)
async def toggle_portfolio(uid: str = Depends(get_token_user_id)):
    cfg = portfolio_service.get_config(user_id=uid)
    new_val = not cfg.get("portfolio_show", False)
    portfolio_service.save_config({"portfolio_show": new_val}, user_id=uid)
    return {"message": f"个人主页展示已{'开启' if new_val else '关闭'}", "portfolio_show": new_val}

@router.get("/portfolio/status", response_model=PortfolioStatusResponse)
async def get_portfolio_status(uid: str = Depends(get_token_user_id)):
    cfg = portfolio_service.get_config(user_id=uid)
    return {"portfolio_show": cfg.get("portfolio_show", False)}

@router.get("/resume/preview", response_model=ResumePreviewResponse)
async def preview_resume(current_user: User = Depends(get_current_user)):
    try:
        from services.ai_service import read_knowledge
        knowledge = read_knowledge(current_user.id)
        content = resume_service.generate_resume_content(str(knowledge))
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成预览失败: {str(e)}")

@router.get("/resumes", response_model=ResumeListResponse)
async def get_resumes(current_user: User = Depends(get_current_user)):
    try:
        from services.database import SessionLocal
        from services.resume_service import ResumeService
        db = SessionLocal()
        try:
            rs = ResumeService(db=db)
            resumes = rs.get_resumes(user_id=current_user.id)
            return {"resumes": resumes}
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取简历列表失败: {str(e)}")

@router.get("/resumes/{resume_id}/view")
async def view_resume_html(resume_id: int, template: str = "modern", uid: str = Depends(get_token_user_id), role: str = Depends(get_token_role)):
    try:
        resume = resume_service.get_resume_by_id(resume_id, user_id=uid if role != "super_admin" else "")
        if not resume:
            raise HTTPException(status_code=404, detail="简历不存在")
        if role != "super_admin" and resume.user_id != uid:
            raise HTTPException(status_code=403, detail="无权访问该简历")
        content = resume.content or ""
        from services.resume_templates import render_resume as render_tmpl
        html_str = render_tmpl(content, template)
        from fastapi.responses import Response
        html_bytes = html_str.encode('utf-8')
        return Response(content=html_bytes, media_type="text/html", headers={"Content-Length": str(len(html_bytes))})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预览失败: {str(e)}")


def _resolve_user_id(token: str = "", authorization: str = ""):
    """从 query token 或 Authorization header 解析 user_id，兼容 window.open 无 header 场景。"""
    _token = token or authorization.replace("Bearer ", "")
    if _token:
        try:
            payload = jwt.decode(_token, settings.SECRET_KEY, algorithms=["HS256"])
            return payload.get("user_id", ""), payload.get("role", "user")
        except Exception:
            pass
    return "", "user"

@router.get("/resumes/{resume_id}/download")
async def download_resume_pdf(resume_id: int, template: str = "modern", token: str = "",
    authorization: str = Header("")):
    uid, role = _resolve_user_id(token, authorization)
    try:
        resume = resume_service.get_resume_by_id(resume_id, user_id=uid if role != "super_admin" else "")
        if not resume:
            raise HTTPException(status_code=404, detail="简历不存在")
        if role != "super_admin" and resume.user_id != uid:
            raise HTTPException(status_code=403, detail="无权访问该简历")
        from services.resume_templates import render_resume as render_tmpl
        resume_html = render_tmpl(resume.content, template)
        import asyncio
        pdf_bytes = await _generate_pdf_async(resume_html)
        pdf_data = bytes(pdf_bytes)
        from fastapi.responses import Response
        from urllib.parse import quote
        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(resume.filename)}",
                "Content-Length": str(len(pdf_data))
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")

@router.get("/stats", response_model=StatsSummaryResponse)
async def get_stats(uid: str = Depends(get_token_user_id), role: str = Depends(get_token_role), db: DBSession = Depends(get_db)) -> StatsSummaryResponse:
    from services.repository.container import RepoContainer
    repo = RepoContainer(db)
    is_admin = role == "super_admin"
    user_filter = {} if is_admin else {"user_id": uid}
    
    visit_count = repo.stats.count(event_type=EventType.VISIT, **user_filter)
    chat_count = repo.stats.count(event_type=EventType.CHAT, **user_filter)
    download_count = repo.stats.count(event_type=EventType.DOWNLOAD, **user_filter)
    portfolio_count = repo.stats.count(event_type=EventType.PORTFOLIO, **user_filter)

    beijing_tz = timezone(timedelta(hours=8))
    sessions = repo.session.list_all() if is_admin else repo.session.list(user_id=uid)
    sessions.sort(key=lambda s: s.created_at or datetime.min, reverse=True)
    session_stats = []
    for s in sessions:
        conv_count = repo.conversation.count(session_id=s.id, role="user", **(user_filter if not is_admin else {}))
        dl_count = repo.stats.count(session_id=s.id, event_type=EventType.DOWNLOAD, **user_filter)
        created = s.created_at
        if created:
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            created = created.astimezone(beijing_tz)
            created_str = created.strftime("%Y-%m-%d %H:%M:%S")
        else:
            created_str = None
        session_stats.append({
            "session_id": s.id,
            "created_at": created_str,
            "conversation_count": conv_count,
            "download_count": dl_count
        })

    return StatsSummaryResponse(
        visit_count=visit_count,
        chat_count=chat_count,
        download_count=download_count,
        portfolio_count=portfolio_count,
        sessions=[StatsSessionItem(**s) for s in session_stats],
    )

@router.get("/stats/questions", response_model=QuestionStatsResponse)
async def get_question_stats(uid: str = Depends(get_token_user_id), role: str = Depends(get_token_role), db: DBSession = Depends(get_db)) -> QuestionStatsResponse:
    from services.repository.container import RepoContainer
    repo = RepoContainer(db)
    user_filter = None if role == "super_admin" else uid
    questions = repo.conversation.count_by_question(user_id=user_filter, limit=20)
    return QuestionStatsResponse(
        questions=[QuestionStatsItem(question=q[0], count=q[1]) for q in questions]
    )


@router.post("/stats/questions/add", response_model=QuestionAddResponse)
async def add_question_to_knowledge(req: QuestionAddRequest, uid: str = Depends(get_token_user_id), db: DBSession = Depends(get_db)) -> QuestionAddResponse:
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    from config import get_user_knowledge_dir
    knowledge_dir = get_user_knowledge_dir(uid)
    os.makedirs(knowledge_dir, exist_ok=True)

    filename = os.path.join(knowledge_dir, "07_高频问题.md")
    new_entry = f"\n## Q：{question}\n**A：** （待补充）\n"
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            existing = f.read()
        if question in existing:
            raise HTTPException(status_code=400, detail="问题已存在于知识库中")
        content = existing + new_entry
    else:
        content = f"# 高频问题统计\n{new_entry}"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    rag_service.load_knowledge()
    return QuestionAddResponse(message="已添加到知识库")


@router.post("/stats/clear", response_model=StatsClearResponse)
async def clear_stats(uid: str = Depends(get_token_user_id), role: str = Depends(get_token_role), db: DBSession = Depends(get_db)) -> StatsClearResponse:
    from services.repository.container import RepoContainer
    repo = RepoContainer(db)
    if role == "super_admin":
        repo.conversation.delete_all()
        repo.session.delete_all()
        repo.stats.delete_all()
    else:
        repo.conversation.delete_by_user(uid)
        repo.session.delete_by_user(uid)
        repo.stats.delete_by_user(uid)
    db.commit()

    import os
    from config import get_user_knowledge_dir
    knowledge_dir = get_user_knowledge_dir(uid) if role != "super_admin" else settings.KNOWLEDGE_DIR
    stats_file = os.path.join(knowledge_dir, "07_高频问题统计.md")
    if os.path.exists(stats_file):
        os.remove(stats_file)

    return StatsClearResponse(message="统计数据已清除")

@router.get("/sessions", response_model=SessionListResponse)
async def get_sessions(current_user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    from services.repository.container import RepoContainer
    uid = current_user.id
    role = current_user.role
    repo = RepoContainer(db)
    if role == "super_admin":
        sessions = repo.session.list_all()
    else:
        sessions = repo.session.list(user_id=uid)
        sessions.sort(key=lambda s: s.created_at or datetime.min, reverse=True)
    return {
        "sessions": [
            {
                "id": s.id,
                "created_at": format_beijing_time(s.created_at),
                "last_active": format_beijing_time(s.last_active),
                "is_active": s.is_active
            }
            for s in sessions
        ]
    }

@router.get("/sessions/{session_id}/conversations", response_model=ConversationListResponse)
async def get_conversations(session_id: str, current_user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    from services.repository.container import RepoContainer
    uid = current_user.id
    role = current_user.role
    repo = RepoContainer(db)
    conversations = repo.conversation.list_by_session(session_id)
    if role != "super_admin" and uid:
        conversations = [c for c in conversations if c.user_id == uid]
    return {
        "conversations": [
            {
                "role": c.role,
                "content": c.content,
                "created_at": format_beijing_time(c.created_at)
            }
            for c in conversations
        ]
    }

@router.get("/prompt/resume", response_model=PromptResponse)
async def get_resume_prompt(current_user: User = Depends(require_super_admin)):
    content = prompt_manager.get("resume_prompt", settings.RESUME_PROMPT)
    return PromptResponse(content=content)

@router.get("/prompt/agent", response_model=PromptResponse)
async def get_agent_prompt(current_user: User = Depends(require_super_admin)):
    content = getattr(settings, "AGENT_PROMPT", "")
    if not content:
        from services.agent_service import DEFAULT_AGENT_PROMPT
        content = DEFAULT_AGENT_PROMPT
    return PromptResponse(content=content)

@router.post("/prompt/agent", response_model=MessageResponse)
async def update_agent_prompt(req: PromptRequest, current_user: User = Depends(require_super_admin)):
    settings.AGENT_PROMPT = req.content
    _save_config("app_config", {"agent_prompt": req.content})
    return {"message": "Agent提示词已更新"}

@router.post("/prompt/resume", response_model=MessageResponse)
async def update_resume_prompt(req: PromptRequest, current_user: User = Depends(require_super_admin)):
    prompt_manager.update(
        key="resume_prompt",
        content=req.content,
        change_log="管理员后台更新",
        created_by="admin",
    )
    settings.RESUME_PROMPT = req.content
    _save_config("app_config", {"resume_prompt": req.content})
    return {"message": "简历提示词已更新"}

@router.get("/prompt/visitor", response_model=PromptResponse)
async def get_visitor_prompt(current_user: User = Depends(require_super_admin)):
    content = prompt_manager.get("visitor_system_prompt", settings.VISITOR_SYSTEM_PROMPT_TEMPLATE)
    return PromptResponse(content=content)

@router.post("/prompt/visitor", response_model=MessageResponse)
async def update_visitor_prompt(req: PromptRequest, current_user: User = Depends(require_super_admin)):
    prompt_manager.update(
        key="visitor_system_prompt",
        content=req.content,
        change_log="管理员后台更新",
        created_by="admin",
    )
    settings.VISITOR_SYSTEM_PROMPT_TEMPLATE = req.content
    _save_config("app_config", {"visitor_system_prompt_template": req.content})
    return {"message": "访客系统提示词已更新"}

class WelcomeConfigResponse(BaseModel):
    greeting: str
    self_intro: str
    quick_questions: str
    initial_message: str
    resume_show: bool

class WelcomeConfigUpdateRequest(BaseModel):
    greeting: Optional[str] = None
    self_intro: Optional[str] = None
    quick_questions: Optional[str] = None
    initial_message: Optional[str] = None

def _load_config(category: str, user_id: str = "") -> dict:
    """Load config from KnowledgeBase KV store."""
    from services.database import SessionLocal
    from services.repository.container import RepoContainer
    db = SessionLocal()
    try:
        return RepoContainer(db).knowledge_base.get_data_dict(user_id, category)
    except Exception:
        pass
    finally:
        db.close()
    return {}

def _save_config(category: str, data: dict, user_id: str = ""):
    """Save config to KnowledgeBase KV store (merge with existing)."""
    from services.database import SessionLocal
    from services.repository.container import RepoContainer
    db = SessionLocal()
    try:
        RepoContainer(db).knowledge_base.merge_data(user_id, category, data)
    except Exception:
        pass
    finally:
        db.close()


def _save_app_config(data: dict):
    """同步写入 app_configs 表（运行时 LLM 配置读取的来源）。"""
    from services.database import SessionLocal
    from services.repository.container import RepoContainer
    db = SessionLocal()
    try:
        RepoContainer(db).app_config.merge_data("app_config", data)
    except Exception:
        pass
    finally:
        db.close()


@router.get("/welcome-config", response_model=WelcomeConfigResponse)
async def get_welcome_config(uid: str = Depends(get_token_user_id)):
    db_cfg = _load_config("welcome_config", user_id=uid)
    return WelcomeConfigResponse(
        greeting=db_cfg.get("greeting", settings.WELCOME_GREETING),
        self_intro=db_cfg.get("self_intro", settings.WELCOME_SELF_INTRO),
        quick_questions=db_cfg.get("quick_questions", settings.WELCOME_QUICK_QUESTIONS),
        initial_message=db_cfg.get("initial_message", settings.INITIAL_MESSAGE),
        resume_show=settings.RESUME_SHOW
    )

@router.post("/welcome-config", response_model=MessageResponse)
async def update_welcome_config(req: WelcomeConfigUpdateRequest, uid: str = Depends(get_token_user_id)):
    updates = {}
    if req.greeting is not None:
        updates["greeting"] = req.greeting
    if req.self_intro is not None:
        updates["self_intro"] = req.self_intro
    if req.quick_questions is not None:
        updates["quick_questions"] = req.quick_questions
    if req.initial_message is not None:
        updates["initial_message"] = req.initial_message
    if updates:
        _save_config("welcome_config", updates, user_id=uid)
    return {"message": "欢迎配置已更新"}

@router.post("/welcome-config/generate-intro", response_model=GenerateIntroResponse)
async def generate_welcome_intro(uid: str = Depends(get_token_user_id)):
    """Use LLM to generate a self-intro from the knowledge base."""
    from services.knowledge_manager import _get_all_kb_data
    from services.ai_service import llm as gen_llm
    from langchain_core.messages import HumanMessage, SystemMessage
    try:
        kb = _get_all_kb_data()
        name = kb.get("personal_info", {}).get("name", "候选人")
        summary_parts = []
        if kb.get("personal_info", {}).get("self_intro"):
            summary_parts.append(f"个人简介：{kb['personal_info']['self_intro']}")
        work_list = kb.get("work_experience", {}).get("work_list", [])
        for w in work_list:
            company = w.get("company", "")
            period = w.get("period", "")
            position = w.get("position", "")
            desc = w.get("description", "")
            if desc:
                short_desc = desc[:200].replace("<p>", "").replace("</p>", "").replace("<ul>", "").replace("</ul>", "").replace("<li>", "· ")
                summary_parts.append(f"{company}({period}) {position}: {short_desc}")
        context = "\n".join(summary_parts)
        prompt = f"""你正在为求职者生成访客端欢迎页面的自我介绍。根据以下信息，生成一段 80-150 字的自我介绍（第一人称），语言自然亲切，适合求职场景。直接输出文案，不要解释、不要加标题。

求职者信息：
{context}"""
        msg = [SystemMessage(content="你擅长生成求职场景的自我介绍文案，简洁自然，突出优势。"), HumanMessage(content=prompt)]
        resp = gen_llm.invoke(msg)
        intro = resp.content.strip()
        msg_prompt = f"""根据以下求职者信息，生成一句初始招呼语（30-50 字），以"您好！"开头，表明身份并邀请提问。

求职者信息：
{context}"""
        msg2 = [SystemMessage(content="你擅长生成友好的求职场景招呼语。"), HumanMessage(content=msg_prompt)]
        resp2 = gen_llm.invoke(msg2)
        init_msg = resp2.content.strip()
        return {"self_intro": intro, "initial_message": init_msg}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@router.get("/knowledge-structured/{category}", response_model=KnowledgeStructuredResponse)
async def get_knowledge_structured(category: str, uid: str = Depends(get_token_user_id), db: DBSession = Depends(get_db)):
    from services.repository.container import RepoContainer
    kb = RepoContainer(db).knowledge_base.get_by_category(uid, category)
    if not kb:
        return {"category": category, "data": {}}
    return {"category": category, "data": json.loads(kb.data)}

@router.post("/knowledge-structured/{category}", response_model=MessageResponse)
async def save_knowledge_structured(category: str, req: KnowledgeDataRequest, uid: str = Depends(get_token_user_id), db: DBSession = Depends(get_db)):
    from services.repository.container import RepoContainer
    RepoContainer(db).knowledge_base.upsert(uid, category, json.dumps(req.data))
    
    # 以下为"尽力而为"的副作用：失败不影响 DB 保存
    try:
        _sync_knowledge_to_md(category, req.data, uid)
    except Exception:
        pass
    
    try:
        rag_service.update_category(category, db)
    except Exception:
        pass
    
    return {"message": "保存成功"}

def _sync_knowledge_to_md(category: str, data: dict, user_id: str = ""):
    import os
    from config import get_user_knowledge_dir
    knowledge_dir = get_user_knowledge_dir(user_id)
    category_map = {
        "personal_info": "01_个人信息",
        "education": "02_教育背景",
        "work_experience": "03_工作经历",
        "projects": "04_项目经历",
        "skills": "05_专业技能栈",
        "faq": "06_HR高频问答库",
        "stats": "07_高频问题统计"
    }
    filename = category_map.get(category, category)
    filepath = os.path.join(knowledge_dir, f"{filename}.md")
    
    content = _generate_md_content(category, data)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def _generate_md_content(category: str, data: dict) -> str:
    import json
    if category == "personal_info":
        lines = ["## 个人信息"]
        field_map = {
            "name": "姓名", "age": "年龄", "city": "所在城市",
            "email": "邮箱", "phone": "电话", "github": "GitHub",
            "wechat_name": "微信昵称", "wechat_qr": "微信二维码图片",
            "work_years": "工作年限", "current_status": "当前状态",
            "target_position": "意向岗位", "expected_location": "期望工作地点",
            "start_date": "到岗时间", "salary_expectation": "薪资期望范围"
        }
        for eng, chn in field_map.items():
            v = data.get(eng) or data.get("basic_info", {}).get(eng, "")
            if v: lines.append(f"- {chn}：{v}")
        tags = data.get("job_tags", [])
        if tags:
            lines.append("")
            lines.append("## 职业标签")
            for i, t in enumerate(tags):
                lines.append(f"- 核心标签{i+1}：{t}")
        intro = data.get("self_intro") or data.get("intro", "")
        if intro:
            lines.append("")
            lines.append("## 个人简介")
            lines.append(intro)
        return "\n".join(lines)
    elif category == "education":
        lines = ["## 教育背景"]
        for edu in data.get("education_list", []):
            lines.append(f"- **{edu.get('school', '')}** ({edu.get('period', '')}): {edu.get('degree', '')}")
        return "\n".join(lines)
    elif category == "work_experience":
        lines = ["## 工作经历"]
        for work in data.get("work_list", []):
            lines.append(f"### {work.get('company', '')} ({work.get('period', '')})")
            lines.append(f"- 职位: {work.get('position', '')}")
            if work.get('description'):
                lines.append(f"- {work['description']}")
        return "\n".join(lines)
    elif category == "projects":
        lines = ["## 项目经历"]
        for proj in data.get("project_list", []):
            lines.append(f"### {proj.get('name', '')}")
            lines.append(f"- 角色: {proj.get('role', '')}")
            lines.append(f"- 技术: {proj.get('tech_stack', '')}")
            if proj.get('description'):
                lines.append(f"- {proj['description']}")
        return "\n".join(lines)
    elif category == "skills":
        lines = ["## 专业技能栈"]
        if "skill_groups" in data:
            for cat, tags in data["skill_groups"].items():
                lines.append(f"- {cat}: {', '.join(tags)}")
        else:
            label_map = {"hard_skills": "硬技能", "soft_skills": "软技能", "tool_skills": "工具平台"}
            for key in ["hard_skills", "soft_skills", "tool_skills"]:
                tags = data.get(key, [])
                if tags:
                    label = label_map.get(key, key)
                    lines.append(f"- {label}: {', '.join(tags)}")
        return "\n".join(lines)
    elif category == "faq":
        lines = ["## HR高频问答库"]
        for qa in data.get("faq_list", []):
            lines.append(f"**Q: {qa.get('question', '')}**")
            lines.append(f"A: {qa.get('answer', '')}")
            lines.append("")
        return "\n".join(lines)
    elif category == "stats":
        lines = ["## 高频问题统计"]
        for q in data.get("questions", []):
            lines.append(f"- {q.get('question', '')}: {q.get('count', 0)}次")
        return "\n".join(lines)
    return str(data)

@router.post("/kb/preview", response_model=KnowledgePreviewResponse)
async def knowledge_preview(req: KnowledgePreviewRequest, uid: str = Depends(get_token_user_id)):
    from services.knowledge_manager import preview as km_preview
    try:
        text = req.content
        if not text:
            raise HTTPException(status_code=400, detail="请输入要修改的内容")
        result = km_preview(text, uid)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.post("/kb/confirm", response_model=KnowledgeConfirmResponse)
async def knowledge_confirm(req: KnowledgeConfirmRequest, uid: str = Depends(get_token_user_id)):
    """
    确认执行预览中的变更。
    """
    from services.knowledge_manager import confirm as km_confirm
    preview_id = req.preview_id
    if not preview_id:
        raise HTTPException(status_code=400, detail="请提供预览ID")
    result = km_confirm(preview_id, uid)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/kb/regenerate-faq", response_model=KnowledgeConfirmResponse)
async def knowledge_regenerate_faq(uid: str = Depends(get_token_user_id)):
    """
    基于当前知识库内容，重新生成FAQ（保留问题模板，重写答案）。
    """
    from services.knowledge_manager import regenerate_faq as km_regenerate_faq
    result = km_regenerate_faq(uid)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@router.post("/kb/rebuild-vector", response_model=MessageResponse)
async def rebuild_vector_store(uid: str = Depends(get_token_user_id), db: DBSession = Depends(get_db)):
    rag_service.build_main_with_mapping(db, user_id=uid)
    dirs = json.loads(settings.APPENDIX_KNOWLEDGE_DIRS) if settings.APPENDIX_KNOWLEDGE_DIRS else []
    for d in dirs:
        if os.path.isdir(d):
            appendix_docs = rag_service.load_appendix_knowledge(d)
            if appendix_docs:
                rag_service.add_appendix_to_store(appendix_docs)
    rag_service.init_qa_chain()
    return {"message": "向量库重建完成"}


@router.post("/kb/clear-faq-answers", response_model=MessageResponse)
async def clear_faq_answers(uid: str = Depends(get_token_user_id), db: DBSession = Depends(get_db)):
    from services.repository.container import RepoContainer
    repo = RepoContainer(db)
    kb = repo.knowledge_base.get_by_category(uid, "faq")
    if kb and kb.data:
        data = json.loads(kb.data)
        if isinstance(data, dict):
            for item in data.get("faq_list", []):
                item["answer"] = ""
            kb.data = json.dumps(data)
            db.commit()
    return {"message": "FAQ 答案已清空"}


@router.post("/appendix/add-path", response_model=AppendixUploadResponse)
async def add_appendix_knowledge(req: AddAppendixPathRequest, current_user: User = Depends(require_super_admin)):
    dir_path = req.path.strip()
    if not dir_path:
        raise HTTPException(status_code=400, detail="请提供目录路径")
    if not os.path.isdir(dir_path):
        raise HTTPException(status_code=400, detail=f"目录不存在: {dir_path}")
    
    appendix_docs = rag_service.load_appendix_knowledge(dir_path)
    if not appendix_docs:
        raise HTTPException(status_code=400, detail="该目录下未找到 Markdown 文件")
    
    count = rag_service.add_appendix_to_store(appendix_docs)
    rag_service.init_qa_chain()
    
    dirs = json.loads(settings.APPENDIX_KNOWLEDGE_DIRS) if settings.APPENDIX_KNOWLEDGE_DIRS else []
    if dir_path not in dirs:
        dirs.append(dir_path)
    settings.APPENDIX_KNOWLEDGE_DIRS = json.dumps(dirs)
    
    return {"message": f"成功存入 {count} 个文档片段到向量库", "count": count, "dir_path": dir_path}


@router.get("/appendix/dirs", response_model=AppendixDirsResponse)
async def get_appendix_dirs(current_user: User = Depends(require_super_admin)):
    dirs = json.loads(settings.APPENDIX_KNOWLEDGE_DIRS) if settings.APPENDIX_KNOWLEDGE_DIRS else []
    return {"dirs": dirs}


@router.delete("/appendix/dirs", response_model=MessageResponse)
async def remove_appendix_dir(req: RemoveAppendixDirRequest, current_user: User = Depends(require_super_admin)):
    target = req.path.strip()
    if not target:
        raise HTTPException(status_code=400, detail="请提供目录路径")
    dirs = json.loads(settings.APPENDIX_KNOWLEDGE_DIRS) if settings.APPENDIX_KNOWLEDGE_DIRS else []
    if target in dirs:
        dirs.remove(target)
    settings.APPENDIX_KNOWLEDGE_DIRS = json.dumps(dirs)
    return {"message": f"已移除目录: {target}", "dirs": dirs}


@router.get("/appendix/info", response_model=AppendixInfoResponse)
async def get_appendix_info(current_user: User = Depends(require_super_admin)):
    info = rag_service.get_appendix_info()
    dirs = json.loads(settings.APPENDIX_KNOWLEDGE_DIRS) if settings.APPENDIX_KNOWLEDGE_DIRS else []
    info["configured_dirs"] = dirs
    return info


APPENDIX_STORAGE_DIR = os.path.join(settings.USER_DATA_DIR, "%s", "appendix_uploads")


def _get_appendix_storage_dir(user_id: str = "") -> str:
    """Per-user appendix storage directory."""
    base = APPENDIX_STORAGE_DIR % user_id if user_id else os.path.join(os.path.dirname(settings.DATABASE_PATH), "appendix_uploads")
    os.makedirs(base, exist_ok=True)
    return base


@router.post("/appendix/upload", response_model=AppendixUploadResponse)
async def upload_appendix_knowledge(
    current_user: User = Depends(get_current_user),
    files: List[UploadFile] = File(...),
    db: DBSession = Depends(get_db)
):
    uid = current_user.id
    md_files = [f for f in files if f.filename and f.filename.endswith('.md')]
    if not md_files:
        raise HTTPException(status_code=400, detail="未找到 Markdown 文件，请选择 .md 文件上传")
    
    from datetime import datetime
    record_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    storage_dir = os.path.join(_get_appendix_storage_dir(uid), record_id)
    os.makedirs(storage_dir, exist_ok=True)
    
    for f in md_files:
        safe_path = f.filename.replace('\\', '/')
        target = os.path.join(storage_dir, safe_path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        content = await f.read()
        with open(target, 'wb') as out:
            out.write(content)
    
    appendix_docs = rag_service.load_appendix_knowledge(storage_dir)
    if not appendix_docs:
        shutil.rmtree(storage_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="文件内容解析后无有效文档片段")
    
    doc_ids = rag_service.add_appendix_to_store(appendix_docs)
    rag_service.init_qa_chain()
    
    file_names = sorted(set(f.filename.replace('\\', '/').split('/')[-1] for f in md_files))
    records = _load_user_appendix_records(db, uid)
    records.append({
        "id": record_id,
        "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "file_count": len(md_files),
        "chunk_count": len(doc_ids),
        "files": file_names[:20],
        "doc_ids": doc_ids
    })
    _save_user_appendix_records(db, uid, records[-50:])
    
    return {"message": f"✅ 成功存入 {len(doc_ids)} 个文档片段到向量库（{len(md_files)} 个文件）", "count": len(doc_ids), "files": len(md_files)}


def _load_user_appendix_records(db, user_id: str) -> list:
    from services.repository.container import RepoContainer
    kb = RepoContainer(db).knowledge_base.get_by_category(user_id, f"appendix_records_{user_id}")
    return json.loads(kb.data) if kb and kb.data else []

def _save_user_appendix_records(db, user_id: str, records: list):
    from services.repository.container import RepoContainer
    RepoContainer(db).knowledge_base.upsert(user_id, f"appendix_records_{user_id}", json.dumps(records))


@router.get("/appendix/records", response_model=AppendixRecordsResponse)
async def get_upload_records(current_user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    records = _load_user_appendix_records(db, current_user.id)
    return {"records": records}


@router.delete("/appendix/records/{record_id}", response_model=MessageResponse)
async def delete_upload_record(record_id: str, current_user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    records = _load_user_appendix_records(db, current_user.id)
    target = None
    for r in records:
        if r.get("id") == record_id:
            target = r
            break
    if not target:
        raise HTTPException(status_code=404, detail="记录未找到")
    
    doc_ids = target.get("doc_ids", [])
    if doc_ids:
        rag_service.remove_by_ids(doc_ids)
        rag_service.init_qa_chain()
    
    new_records = [r for r in records if r.get("id") != record_id]
    _save_user_appendix_records(db, current_user.id, new_records)
    
    storage_path = target.get("storage_path", "")
    if storage_path and os.path.isdir(storage_path):
        shutil.rmtree(storage_path, ignore_errors=True)
    
    return {"message": "记录已删除，向量数据已同步移除"}


@router.post("/appendix/clear", response_model=MessageResponse)
async def clear_all_appendix(current_user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    uid = current_user.id
    records = _load_user_appendix_records(db, uid)
    all_ids = []
    for r in records:
        ids = r.get("doc_ids", [])
        all_ids.extend(ids)
    if all_ids:
        rag_service.remove_by_ids(all_ids)
    
    user_storage = _get_appendix_storage_dir(uid)
    if os.path.isdir(user_storage):
        shutil.rmtree(user_storage, ignore_errors=True)
    
    _save_user_appendix_records(db, uid, [])
    settings.APPENDIX_KNOWLEDGE_DIRS = "[]"
    rag_service.init_qa_chain()
    return {"message": "已清空所有附录数据，向量库已重置"}


@router.post("/list-directories", response_model=DirectoriesResponse)
async def list_directories(req: ListDirectoriesRequest, current_user: User = Depends(require_super_admin)):
    parent_path = req.path or "/"
    if not parent_path:
        parent_path = "/"
    try:
        entries = []
        for entry in sorted(os.listdir(parent_path)):
            full_path = os.path.join(parent_path, entry)
            if os.path.isdir(full_path) and not entry.startswith('.'):
                entries.append({
                    "name": entry,
                    "path": full_path
                })
        return {"entries": entries, "parent": parent_path}
    except Exception as e:
        return {"entries": [], "parent": parent_path, "error": str(e)}


# ============================================================
# Job Radar / JD Matching
# ============================================================

from services.models import CrawledJob
from services.jd_matcher import match_jd
from datetime import datetime as dt


class JobAddRequest(BaseModel):
    title: str
    company: str = ""
    city: str = ""
    salary: str = ""
    jd_text: str = ""
    jd_url: str = ""
    platform: str = "manual"
    jd_parsed: str = ""
    work_address: str = ""


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    status: str = "",
    min_score: int = 0,
    keyword: str = "",
    uid: str = Depends(get_token_user_id),
    role: str = Depends(get_token_role),
    db: DBSession = Depends(get_db),
):
    query = db.query(CrawledJob)
    if role != "super_admin":
        query = query.filter(CrawledJob.user_id == uid)
    if status:
        query = query.filter(CrawledJob.status == status)
    if min_score > 0:
        query = query.filter(
            CrawledJob.match_score.isnot(None),
            CrawledJob.match_score >= min_score,
        )
    if keyword:
        query = query.filter(
            CrawledJob.title.contains(keyword) |
            CrawledJob.company.contains(keyword) |
            CrawledJob.jd_text.contains(keyword)
        )
    jobs = query.order_by(CrawledJob.created_at.desc()).all()
    return {
        "jobs": [
            {
                "id": j.id,
                "platform": j.platform,
                "title": j.title,
                "company": j.company,
                "city": j.city,
                "salary": j.salary,
                "jd_url": j.jd_url,
                "work_address": j.work_address,
                "match_score": j.match_score,
                "match_detail": json.loads(j.match_detail) if j.match_detail else None,
                "status": j.status,
                "created_at": format_beijing_time(j.created_at),
            }
            for j in jobs
        ]
    }


@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job(job_id: int, uid: str = Depends(get_token_user_id), role: str = Depends(get_token_role), db: DBSession = Depends(get_db)):
    job = db.query(CrawledJob).filter(CrawledJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")
    if role != "super_admin" and job.user_id != uid:
        raise HTTPException(status_code=403, detail="无权访问")
    return {
        "id": job.id,
        "platform": job.platform,
        "title": job.title,
        "company": job.company,
        "city": job.city,
        "salary": job.salary,
        "jd_text": job.jd_text,
        "jd_url": job.jd_url,
        "jd_parsed": json.loads(job.jd_parsed) if job.jd_parsed else None,
        "work_address": job.work_address,
        "match_score": job.match_score,
        "match_detail": json.loads(job.match_detail) if job.match_detail else None,
        "status": job.status,
        "created_at": format_beijing_time(job.created_at),
        "updated_at": format_beijing_time(job.updated_at),
    }


@router.post("/jobs", response_model=JobAddResponse)
async def add_job(req: JobAddRequest, uid: str = Depends(get_token_user_id), db: DBSession = Depends(get_db)):
    job = CrawledJob(
        user_id=uid,
        platform=req.platform,
        title=req.title,
        company=req.company,
        city=req.city,
        salary=req.salary,
        jd_text=req.jd_text,
        jd_url=req.jd_url,
        jd_parsed=req.jd_parsed,
        work_address=req.work_address,
        status="new",
    )
    db.add(job)
    db.commit()
    return {"message": "岗位已添加", "id": job.id}


@router.post("/jobs/{job_id}/match", response_model=JobMatchResponse)
async def match_single_job(job_id: int, uid: str = Depends(get_token_user_id), role: str = Depends(get_token_role), db: DBSession = Depends(get_db)):
    job = db.query(CrawledJob).filter(CrawledJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")
    if role != "super_admin" and job.user_id != uid:
        raise HTTPException(status_code=403, detail="无权访问")
    if not job.jd_text:
        raise HTTPException(status_code=400, detail="JD 文本为空，无法匹配")
    crawler_parsed = json.loads(job.jd_parsed) if job.jd_parsed else None
    result = await asyncio.to_thread(
        match_jd, job.jd_text,
        salary_str=job.salary or "", city_str=job.city or "",
        crawler_parsed=crawler_parsed, work_address=job.work_address or "")
    job.match_score = int(result["score"])
    job.match_detail = json.dumps(result, ensure_ascii=False)
    job.jd_parsed = json.dumps(result.get("jd_parsed", {}), ensure_ascii=False)
    job.status = "matched"
    db.commit()
    return {"message": "匹配完成", "score": result["score"], "detail": result}


@router.post("/jobs/batch-match", response_model=JobBatchMatchResponse)
async def match_all_jobs(req: JobBatchMatchRequest = None, uid: str = Depends(get_token_user_id), role: str = Depends(get_token_role), db: DBSession = Depends(get_db)):
    query = db.query(CrawledJob)
    if role != "super_admin":
        query = query.filter(CrawledJob.user_id == uid)
    if req and req.ids:
        jobs = query.filter(CrawledJob.id.in_(req.ids), CrawledJob.jd_text != "").all()
    else:
        jobs = query.filter(
            CrawledJob.status.in_(["new"]),
            CrawledJob.jd_text != "",
        ).all()
    results = []
    for job in jobs:
        if job.status in ("matched", "applied"):
            continue
        try:
            crawler_parsed = json.loads(job.jd_parsed) if job.jd_parsed else None
            result = await asyncio.to_thread(
                match_jd, job.jd_text,
                salary_str=job.salary or "", city_str=job.city or "",
                crawler_parsed=crawler_parsed)
            job.match_score = result["score"]
            job.match_detail = json.dumps(result, ensure_ascii=False)
            job.jd_parsed = json.dumps(result.get("jd_parsed", {}), ensure_ascii=False)
            job.status = "matched"
            results.append({"id": job.id, "score": result["score"]})
        except Exception as e:
            results.append({"id": job.id, "error": str(e)})
    db.commit()
    return {"message": f"已匹配 {len(results)} 个岗位", "results": results}


@router.delete("/jobs/{job_id}", response_model=MessageResponse)
async def delete_job(job_id: int, uid: str = Depends(get_token_user_id), role: str = Depends(get_token_role), db: DBSession = Depends(get_db)):
    job = db.query(CrawledJob).filter(CrawledJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")
    if role != "super_admin" and job.user_id != uid:
        raise HTTPException(status_code=403, detail="无权访问")
    db.delete(job)
    db.commit()
    return {"message": "已删除"}


MATCH_THRESHOLD = 60  # 匹配度达到此分数的岗位自动标记为 matched（低于此仍入库标记为 new）

# 招聘平台常见的"已停招"关键字
EXPIRED_KEYWORDS = [
    "已停止招聘", "该职位已停止", "职位已关闭", "已下线", "暂不招聘",
    "停止招聘", "职位过期", "该岗位已关闭", "招聘已结束", "不再招聘",
    "该职位已暂停", "职位已失效", "已经暂停招聘",
]


def _is_expired(jd_text: str) -> bool:
    """检测 JD 文本是否包含已停招/已下架标记。"""
    if not jd_text:
        return False
    text_lower = jd_text.lower()
    for kw in EXPIRED_KEYWORDS:
        if kw.lower() in text_lower:
            return True
    return False


async def _run_matching(job_ids: list[int], uid: str):
    """Background matching for crawled jobs."""
    from services.database import SessionLocal
    from services.jd_matcher import match_jd
    print(f"[bg_match] starting for {len(job_ids)} jobs")
    db = SessionLocal()
    try:
        for job_id in job_ids:
            job = db.query(CrawledJob).filter(
                CrawledJob.id == job_id, CrawledJob.user_id == uid
            ).first()
            if not job or not job.jd_text:
                continue
            try:
                result = await asyncio.to_thread(
                    match_jd, job.jd_text,
                    salary_str=job.salary or "",
                    city_str=job.city or "",
                    work_address=job.work_address or "",
                    user_id=uid)
                job.match_score = int(result.get("score", 0))
                job.match_detail = json.dumps(result, ensure_ascii=False)
                jd_parsed = result.get("jd_parsed", {})
                if jd_parsed:
                    job.jd_parsed = json.dumps(jd_parsed, ensure_ascii=False)
                job.status = "matched"
                print(f"[bg_match] job#{job_id} score={job.match_score}")
            except Exception as e:
                print(f"[bg_match] job#{job_id} error: {e}")
                job.status = "matched"
                job.match_detail = json.dumps({"error": str(e)}, ensure_ascii=False)
            db.commit()
    finally:
        db.close()
    print(f"[bg_match] done")


@router.post("/jobs/crawl", response_model=CrawlJobsResponse)
async def crawl_jobs(req: CrawlJobsRequest, uid: str = Depends(get_token_user_id), db: DBSession = Depends(get_db)):
    """
    自动抓取招聘岗位。支持实时匹配过滤、去重、停招检测。

    流程：爬取 → 去重(jd_url) → 停招检测 → match_jd() 打分 → 低于阈值丢弃 → 入库
    """
    keywords = req.keywords
    city = req.city
    platform = req.platform
    target_count = min(req.max_count, 20)
    fetch_count = target_count
    sort = req.sort
    if not keywords:
        raise HTTPException(status_code=400, detail="请提供搜索关键词")

    # 用于去重缓存（爬虫内部会查一轮，这里用作回退路径和二次校验）
    existing_urls: set = set()
    existing_keys: set = set()

    # ── 1. 爬取 ──
    from services.jd_matcher import match_jd

    jobs_data = []

    # 主方案：通过 Kimi WebBridge 在真实浏览器中爬取
    import time as _t
    _t0 = _t.time()
    try:
        from services.crawler_client import crawl_via_worker
        existing_urls = {row[0] for row in db.query(CrawledJob.jd_url).filter(
            CrawledJob.jd_url != "", CrawledJob.jd_url.isnot(None)
        ).all() if row[0]}
        skip_titles = db.query(CrawledJob.title, CrawledJob.company).filter(
            CrawledJob.user_id == uid
        ).all()
        existing_keys = {f"{t}|{c}" for t, c in skip_titles if t and c}
        print(f"[crawl] starting Kimi crawl, keyword={keywords} city={city} platform={platform} fetch_count={fetch_count}")
        kimi_jobs = await crawl_via_worker(keywords, city, platform, fetch_count, existing_urls, existing_keys)
        print(f"[crawl] Kimi returned {len(kimi_jobs)} jobs in {_t.time()-_t0:.1f}s")
        if kimi_jobs:
            jobs_data = kimi_jobs
    except asyncio.TimeoutError:
        print(f"[crawl] Kimi WebBridge 超时（60s），准备降级")
    except Exception as e:
        import traceback
        print(f"[crawl] Kimi WebBridge 爬取失败: {e}\n{traceback.format_exc()}")

    # 回退到直连 51job API（HTML 解析）
    if not jobs_data:
        try:
            import httpx as hp, re
            city_code = {"北京": "010000", "上海": "020000", "广州": "030000", "深圳": "040000",
                         "杭州": "080000", "成都": "090000", "武汉": "170000", "南京": "070000",
                         "西安": "260000", "苏州": "060000", "天津": "050000", "重庆": "100000"}
            cc = city_code.get(city, "080000")
            resp = hp.get(
                "https://search.51job.com/jobsearch/search_result.php",
                params={"keyword": keywords, "jobarea": cc, "pagesize": fetch_count,
                        "pageno": 1, "lang": "c", "stype": "2", "postchannel": "0000", "fromJs": "1"},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=15, follow_redirects=True)
            if resp.status_code == 200:
                for card in re.finditer(
                    r'<div[^>]*class="el"[^>]*>.*?<p[^>]*class="t1"[^>]*>.*?href="([^"]+)"[^>]*title="([^"]+)"[^>]*>.*?</p>.*?<span[^>]*class="t2"[^>]*>.*?<a[^>]*>([^<]+)</a>.*?</span>.*?<span[^>]*class="t4"[^>]*>([^<]*)</span>',
                    resp.text, re.S | re.I
                ):
                    job_url = card.group(1).strip()
                    title = re.sub(r'<[^>]+>', '', card.group(2)).strip()
                    company = card.group(3).strip()
                    salary = card.group(4).strip()
                    if title and company:
                        jobs_data.append({
                            "platform": "51job", "title": title, "company": company,
                            "city": city, "salary": salary, "jd_text": "",
                            "jd_url": job_url if "http" in job_url else "https:" + job_url,
                            "jd_parsed": "{}", "work_address": "",
                        })
        except Exception:
            pass

    # 回退到直连 BOSS API
    if not jobs_data:
        try:
            import httpx as hp
            city_code = {"北京": "101010100", "上海": "101020100", "深圳": "101280600",
                         "杭州": "101210100", "广州": "101280100", "成都": "101270100"}.get(city, "")
            url = f"https://www.zhipin.com/wapi/zpgeek/search/joblist.json?query={keywords}&page=1"
            if city_code:
                url += f"&city={city_code}"
            resp = hp.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://www.zhipin.com/",
            }, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("zpData", {}).get("jobList", []):
                    jobs_data.append({
                        "platform": "boss",
                        "title": item.get("jobName", ""),
                        "company": item.get("brandName", ""),
                        "city": item.get("city", {}).get("name", "") if isinstance(item.get("city"), dict) else "",
                        "salary": item.get("salaryDesc", ""),
                        "jd_text": item.get("jobDetail", "") or f"{item.get('jobName','')} {item.get('brandName','')}",
                        "jd_url": f"https://www.zhipin.com/job_detail/{item.get('jobId','')}.html" if item.get('jobId') else "",
                        "jd_parsed": "{}",
                        "work_address": "",
                    })
        except Exception:
            pass

    # 回退到直连 智联招聘 API
    if not jobs_data:
        try:
            import httpx as hp
            import random, time as _time
            city_code = {"北京": "530", "上海": "538", "广州": "763", "深圳": "765",
                         "杭州": "653", "成都": "801", "武汉": "736", "南京": "635",
                         "西安": "854", "苏州": "639", "天津": "531", "重庆": "551"}.get(city, "489")
            ts = int(_time.time() * 1000)
            req_id = f"{ts}-{random.randint(100000, 999999)}"
            params = {"_v": "0.43240637", "x-zp-page-request-id": req_id,
                      "x-zp-client-id": "63ce3555-d2f2-470a-80f4-8538cee76c41"}
            payload = {"cityId": city_code, "kw": keywords, "start": 0, "pageSize": 10,
                       "workExperience": "-1", "education": "-1", "companyType": "-1",
                       "employmentType": "-1", "sortType": 1, "pageNo": 1}
            resp = hp.post("https://fe-api.zhaopin.com/c/i/search/positions",
                           params=params, json=payload,
                           headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                    "Content-Type": "application/json;charset=UTF-8",
                                    "Origin": "https://www.zhaopin.com",
                                    "Referer": "https://www.zhaopin.com/"}, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("data", {}).get("results", []):
                    job_id = item.get("number", "") or str(item.get("positionId", ""))
                    jobs_data.append({
                        "platform": "zhaopin",
                        "title": item.get("title", "") or item.get("name", ""),
                        "company": (item.get("company", {}) or {}).get("name", ""),
                        "city": item.get("city", {}).get("name", "") if isinstance(item.get("city"), dict) else str(item.get("city", "")),
                        "salary": item.get("salary", "") or "",
                        "jd_text": item.get("jobDetail", "") or item.get("description", "") or "",
                        "jd_url": f"https://www.zhaopin.com/position/detail/{job_id}" if job_id else "",
                        "jd_parsed": "{}",
                        "work_address": "",
                    })
        except Exception:
            pass

    if not jobs_data:
        raise HTTPException(status_code=500, detail="未能抓取到岗位数据。可手动添加JD文本，或部署 job-crawler 服务（browser-use）获得完整抓取能力")

    # ── 2. 入库（不匹配） ──
    skipped_dedup = 0
    skipped_expired = 0
    saved = 0
    saved_jobs = []
    print(f"[crawl_save] starting save loop for {len(jobs_data)} jobs")

    for j in jobs_data:
        jd_url = (j.get("jd_url") or "").strip()
        jd_text = (j.get("jd_text") or "").strip()

        # 去重：jd_url + title+company
        title = j.get("title", "").strip()
        company = j.get("company", "").strip()
        key = f"{title}|{company}"
        is_dup = False
        if jd_url and jd_url in existing_urls:
            is_dup = True
        elif title and company and key in existing_keys:
            is_dup = True
        else:
            exists = db.query(CrawledJob.id).filter(
                CrawledJob.jd_url == jd_url, CrawledJob.user_id == uid
            ).first() if jd_url else None
            if exists:
                is_dup = True
            else:
                exists = db.query(CrawledJob.id).filter(
                    CrawledJob.title == title, CrawledJob.company == company,
                    CrawledJob.user_id == uid
                ).first() if title and company else None
                if exists:
                    is_dup = True
        if is_dup:
            print(f"[crawl_save] dedup skip: {title} @ {company} (url={jd_url})")
            skipped_dedup += 1
            if jd_url:
                existing_urls.add(jd_url)
            if title and company:
                existing_keys.add(key)
            continue

        # 停招检测
        if _is_expired(jd_text):
            skipped_expired += 1
            continue

        status_str = "matching" if req.auto_match else "new"
        job = CrawledJob(
            user_id=uid,
            platform=j.get("platform", "boss"),
            title=j.get("title", ""),
            company=j.get("company", ""),
            city=j.get("city", ""),
            salary=j.get("salary", ""),
            jd_text=jd_text,
            jd_url=jd_url,
            jd_parsed=j.get("jd_parsed", "{}"),
            work_address=j.get("work_address", ""),
            match_score=0,
            match_detail="{}",
            status=status_str,
        )
        db.add(job)
        db.flush()
        saved += 1
        saved_jobs.append({**j, "id": job.id, "status": status_str})
        if jd_url:
            existing_urls.add(jd_url)

    db.commit()
    print(f"[crawl_save] saved {saved} jobs, auto_match={req.auto_match}")

    # ── 3. 启动后台匹配 ──
    if req.auto_match and saved_jobs:
        job_ids = [j["id"] for j in saved_jobs]
        asyncio.create_task(_run_matching(job_ids, uid))

    parts = [f"共检索 {len(jobs_data)} 个，入库 {saved} 个"]
    if req.auto_match:
        parts.append("后台匹配中")
    if skipped_dedup:
        parts.append(f"重复 {skipped_dedup}")
    if skipped_expired:
        parts.append(f"停招 {skipped_expired}")
    message = "，".join(parts)

    return {"message": message, "count": saved, "jobs": saved_jobs,
            "skipped_dedup": skipped_dedup, "skipped_expired": skipped_expired}


@router.post("/jobs/crawl-submit", response_model=CrawlSubmitResponse)
async def crawl_submit(req: CrawlSubmitRequest, uid: str = Depends(get_token_user_id), db: DBSession = Depends(get_db)):
    """Receive crawled jobs from local_crawler.py script."""
    jobs_data = req.jobs
    if not jobs_data:
        raise HTTPException(status_code=400, detail="没有岗位数据")
    saved = 0
    for j in jobs_data:
        job = CrawledJob(
            user_id=uid,
            platform=j.platform,
            title=j.title,
            company=j.company,
            city=j.city,
            salary=j.salary,
            jd_text=j.jd_text,
            jd_url=j.jd_url,
            work_address=j.work_address,
            status="matched",
        )
        db.add(job)
        saved += 1
    db.commit()
    return {"message": f"已保存 {saved} 个岗位", "count": saved}


@router.post("/jobs/batch-delete", response_model=MessageResponse)
async def batch_delete_jobs(req: BatchDeleteJobsRequest, uid: str = Depends(get_token_user_id), role: str = Depends(get_token_role), db: DBSession = Depends(get_db)):
    ids = req.ids
    if not ids:
        raise HTTPException(status_code=400, detail="请提供要删除的ID列表")
    query = db.query(CrawledJob).filter(CrawledJob.id.in_(ids))
    if role != "super_admin":
        query = query.filter(CrawledJob.user_id == uid)
    query.delete(synchronize_session=False)
    db.commit()
    return {"message": f"已删除 {len(ids)} 个岗位"}


@router.post("/upload/qrcode", response_model=UploadResponse)
async def upload_qrcode(
    current_user: User = Depends(get_current_user),
    file: UploadFile = File(...),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")
    
    ext = os.path.splitext(file.filename or "qr.png")[1] or ".png"
    filename = f"qrcode_{uuid.uuid4().hex[:8]}{ext}"
    upload_dir = os.path.join(os.path.dirname(settings.DATABASE_PATH), "uploads", "qrcodes")
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)
    
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
    
    url = f"/uploads/qrcodes/{filename}"
    backend_host = os.environ.get("BACKEND_URL", "http://localhost:51666")
    full_url = f"{backend_host}{url}"
    return {"url": full_url, "filename": filename}

