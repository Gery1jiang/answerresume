"""
配置模块。
向后兼容：导出所有旧 config.py 的内容。
新增：load_settings() 返回不可变配置，替代运行时修改 settings。
"""

# ── 向后兼容：旧 config.py 的全部导出 ─────────────────
from config_old import (
    get_knowledge_base_dir,
    get_user_knowledge_dir,
    get_provider_base_url,
    get_candidate_name,
    get_candidate_profile,
    settings as legacy_settings,
    Settings,
    _PROVIDER_BASE_URLS,
)

# ── 新增：不可变配置 API ──────────────────────────────

from dataclasses import dataclass, field
from typing import Optional
import os


@dataclass(frozen=True)
class AppSettings:
    """运行时不可变配置。启动时从 .env + DB 合并创建。"""
    # LLM
    admin_api_key: str = ""
    admin_llm_provider: str = "LongCat"
    admin_llm_model: str = "LongCat-2.0"
    visitor_api_key: str = ""
    visitor_llm_provider: str = "DeepSeek"
    visitor_llm_model: str = "deepseek-v4-flash"

    # Embedding
    siliconflow_api_key: str = ""
    siliconflow_api_base: str = "https://api.siliconflow.cn/v1"
    embedding_model: str = "BAAI/bge-m3"

    # Auth
    admin_username: str = "admin"
    admin_password: str = "admin123"
    visitor_password: str = "AGENTAGENT"
    secret_key: str = "answer-agent-secret-key-2026"

    # Limits
    max_sessions: int = 10
    session_timeout_minutes: int = 120

    # Features
    resume_show: bool = False
    portfolio_show: bool = False

    # API keys
    tavily_api_key: str = ""
    firecrawl_api_key: str = ""
    firecrawl_daily_budget: int = 20
    anysearch_api_key: str = ""
    amap_api_key: str = ""
    visitor_tavily_api_key: str = ""
    visitor_amap_api_key: str = ""

    # Paths
    knowledge_dir: str = ""
    user_data_dir: str = ""
    vector_store_dir: str = ""
    resume_dir: str = ""
    database_path: str = ""
    appendix_knowledge_dirs: str = "[]"
    chromium_path: str = "/usr/bin/chromium"

    # Prompts
    agent_prompt: str = ""
    visitor_prompt_version: int = 1
    visitor_system_prompt_template: str = ""

    # Intent detection LLM (dedicated config, falls back to visitor then admin)
    intent_llm_api_key: str = ""
    intent_llm_provider: str = ""
    intent_llm_model: str = ""

    # Welcome
    welcome_greeting: str = "您好，欢迎您到来"
    welcome_self_intro: str = ""
    welcome_quick_questions: str = ""
    initial_message: str = ""


def load_settings(db_config: dict | None = None) -> AppSettings:
    """从 .env + 可选 DB 配置创建不可变 AppSettings。
    DB 配置优先级高于 .env 默认值。"""
    from config_old import settings as _base

    db = db_config or {}

    return AppSettings(
        admin_api_key=db.get("llm_api_key", _base.ADMIN_API_KEY),
        admin_llm_provider=db.get("llm_provider", _base.ADMIN_LLM_PROVIDER),
        admin_llm_model=db.get("llm_model", _base.ADMIN_LLM_MODEL),
        visitor_api_key=db.get("visitor_llm_api_key", _base.VISITOR_API_KEY),
        visitor_llm_provider=db.get("visitor_llm_provider", _base.VISITOR_LLM_PROVIDER),
        visitor_llm_model=db.get("visitor_llm_model", _base.VISITOR_LLM_MODEL),
        siliconflow_api_key=_base.SILICONFLOW_API_KEY,
        siliconflow_api_base=_base.SILICONFLOW_API_BASE,
        embedding_model=_base.SILICONFLOW_EMBEDDING_MODEL,
        admin_username=_base.ADMIN_USERNAME,
        admin_password=_base.ADMIN_PASSWORD,
        visitor_password=db.get("visitor_password", _base.VISITOR_PASSWORD),
        secret_key=_base.SECRET_KEY,
        max_sessions=int(db.get("max_sessions", _base.MAX_SESSIONS)),
        session_timeout_minutes=int(db.get("session_timeout_minutes", _base.SESSION_TIMEOUT_MINUTES)),
        resume_show=bool(db.get("resume_show", _base.RESUME_SHOW)),
        portfolio_show=_base.PORTFOLIO_SHOW,
        tavily_api_key=_base.TAVILY_API_KEY,
        firecrawl_api_key=_base.FIRECRAWL_API_KEY,
        firecrawl_daily_budget=_base.FIRECRAWL_DAILY_BUDGET,
        anysearch_api_key=_base.ANYSEARCH_API_KEY,
        amap_api_key=db.get("amap_api_key", _base.AMAP_API_KEY),
        visitor_tavily_api_key=db.get("visitor_tavily_api_key", _base.VISITOR_TAVILY_API_KEY),
        visitor_amap_api_key=db.get("visitor_amap_api_key", _base.VISITOR_AMAP_API_KEY),
        knowledge_dir=_base.KNOWLEDGE_DIR,
        user_data_dir=_base.USER_DATA_DIR,
        vector_store_dir=_base.VECTOR_STORE_DIR,
        resume_dir=_base.RESUME_DIR,
        database_path=_base.DATABASE_PATH,
        appendix_knowledge_dirs=db.get("appendix_knowledge_dir", _base.APPENDIX_KNOWLEDGE_DIRS),
        chromium_path=_base.CHROMIUM_PATH,
        intent_llm_api_key=db.get("intent_llm_api_key", ""),
        intent_llm_provider=db.get("intent_llm_provider", ""),
        intent_llm_model=db.get("intent_llm_model", ""),
        agent_prompt=_base.AGENT_PROMPT,
        visitor_prompt_version=int(db.get("visitor_prompt_version", str(_base.VISITOR_PROMPT_VERSION))),
        visitor_system_prompt_template=_base.VISITOR_SYSTEM_PROMPT_TEMPLATE,
        welcome_greeting=_base.WELCOME_GREETING,
        welcome_self_intro=_base.WELCOME_SELF_INTRO,
        welcome_quick_questions=_base.WELCOME_QUICK_QUESTIONS,
        initial_message=_base.INITIAL_MESSAGE,
    )


# 保留旧 settings 引用确保向后兼容
settings = legacy_settings


# ── 共享 LLM 配置读取（DB 优先，env 兜底）───────────────

def get_admin_llm_config() -> dict:
    """管理端 LLM 配置：DB app_configs → env 兜底。"""
    from config_old import _PROVIDER_BASE_URLS
    _api_key = ""
    _provider = ""
    _model = ""
    try:
        from services.database import SessionLocal
        from services.repository.container import RepoContainer
        db = SessionLocal()
        _cfg = RepoContainer(db).app_config.get_data_dict("app_config")
        db.close()
        if _cfg:
            _provider = _cfg.get("llm_provider", "")
            _model = _cfg.get("llm_model", "")
            _api_key = _cfg.get("llm_api_key", "")
    except Exception:
        pass
    if not _api_key:
        _api_key = settings.ADMIN_API_KEY
    if not _provider:
        _provider = settings.ADMIN_LLM_PROVIDER
    if not _model:
        _model = settings.ADMIN_LLM_MODEL
    return {
        "api_key": _api_key,
        "api_base": _PROVIDER_BASE_URLS.get(_provider, "https://api.longcat.chat/openai/v1"),
        "model": _model,
    }


def get_visitor_llm_config() -> dict:
    """访客端 LLM 配置：DB visitor 配置 → env 兜底。"""
    from config_old import _PROVIDER_BASE_URLS
    _api_key = ""
    _provider = ""
    _model = ""
    try:
        from services.database import SessionLocal
        from services.repository.container import RepoContainer
        db = SessionLocal()
        _cfg = RepoContainer(db).app_config.get_data_dict("app_config")
        db.close()
        if _cfg:
            _provider = _cfg.get("visitor_llm_provider", "")
            _model = _cfg.get("visitor_llm_model", "")
            _api_key = _cfg.get("visitor_llm_api_key", "")
    except Exception:
        pass
    if not _api_key:
        _api_key = settings.VISITOR_API_KEY
    if not _provider:
        _provider = settings.VISITOR_LLM_PROVIDER
    if not _model:
        _model = settings.VISITOR_LLM_MODEL
    return {
        "api_key": _api_key,
        "api_base": _PROVIDER_BASE_URLS.get(_provider, "https://api.deepseek.com"),
        "model": _model,
    }


def get_intent_llm_config() -> dict:
    """意图识别 LLM 配置：DB intent_llm_* → env INTENT_LLM_* → visitor → admin 兜底。"""
    from config_old import _PROVIDER_BASE_URLS
    import os

    _api_key = ""
    _provider = ""
    _model = ""
    # Tier 1: DB app_configs
    try:
        from services.database import SessionLocal
        from services.repository.container import RepoContainer
        db = SessionLocal()
        _cfg = RepoContainer(db).app_config.get_data_dict("app_config")
        db.close()
        if _cfg:
            _provider = _cfg.get("intent_llm_provider", _cfg.get("visitor_llm_provider", ""))
            _model = _cfg.get("intent_llm_model", _cfg.get("visitor_llm_model", ""))
            _api_key = _cfg.get("intent_llm_api_key", _cfg.get("visitor_llm_api_key", ""))
    except Exception:
        pass
    if _api_key:
        return {
            "api_key": _api_key,
            "api_base": _PROVIDER_BASE_URLS.get(_provider, "https://api.deepseek.com"),
            "model": _model,
        }
    # Tier 2: env INTENT_LLM_API_KEY / _PROVIDER / _MODEL
    _env_key = os.environ.get("INTENT_LLM_API_KEY", "")
    _env_provider = os.environ.get("INTENT_LLM_PROVIDER", "")
    _env_model = os.environ.get("INTENT_LLM_MODEL", "")
    if _env_key and _env_provider and _env_model:
        return {
            "api_key": _env_key,
            "api_base": _PROVIDER_BASE_URLS.get(_env_provider, "https://api.deepseek.com"),
            "model": _env_model,
        }
    # Tier 3: visitor LLM 配置
    _vcfg = get_visitor_llm_config()
    if _vcfg.get("api_key"):
        return _vcfg
    # Tier 4: admin LLM 配置
    return get_admin_llm_config()
