import os
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_knowledge_base_dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge")

def get_user_knowledge_dir(user_id: str = "") -> str:
    """每用户知识库目录。user_id 为空时返回全局 KNOWLEDGE_DIR (向后兼容)。"""
    if not user_id:
        return settings.KNOWLEDGE_DIR
    return os.path.join(settings.USER_DATA_DIR, user_id, "knowledge")

_PROVIDER_BASE_URLS = {
    "LongCat": "https://api.longcat.chat/openai/v1",
    "DeepSeek": "https://api.deepseek.com/v1",
    "SiliconFlow": "https://api.siliconflow.cn/v1",
    "阿里云": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "百度智能云": "https://qianfan.baidubce.com/v2",
    "字节云": "https://ark.cn-beijing.volces.com/api/v3",
    "腾讯云": "https://hunyuan.tencentcs.com/v2",
    "智谱AI": "https://open.bigmodel.cn/api/paas/v4",
    "百川智能": "https://api.baichuan-ai.com/v1",
    "月之暗面": "https://api.moonshot.cn/v1",
    "OpenAI": "https://api.openai.com/v1",
}

def get_provider_base_url(provider: str) -> str:
    return _PROVIDER_BASE_URLS.get(provider, "https://api.longcat.chat/openai/v1")

def get_candidate_name(user_id: str = "") -> str:
    """Extract candidate name from knowledge base Markdown files."""
    import re
    if user_id:
        name_file = os.path.join(settings.USER_DATA_DIR, user_id, "knowledge", "01_个人信息.md")
    else:
        name_file = os.path.join(get_knowledge_base_dir(), "01_个人信息.md")
    if not os.path.exists(name_file):
        return "候选人"
    try:
        with open(name_file, "r", encoding="utf-8") as f:
            content = f.read()
        m = re.search(r'姓名[：:]\s*(\S+)', content)
        return m.group(1).strip() if m else "候选人"
    except Exception:
        return "候选人"

def get_candidate_profile(user_id: str = "") -> dict:
    """Extract candidate profile (name, city, position, tags) from knowledge base."""
    import re
    if user_id:
        name_file = os.path.join(settings.USER_DATA_DIR, user_id, "knowledge", "01_个人信息.md")
    else:
        name_file = os.path.join(get_knowledge_base_dir(), "01_个人信息.md")
    info = {"name": "候选人", "city": "", "position": "", "tags": []}
    if not os.path.exists(name_file):
        return info
    try:
        with open(name_file, "r", encoding="utf-8") as f:
            content = f.read()
        m_name = re.search(r'姓名[：:]\s*(\S+)', content)
        if m_name:
            info["name"] = m_name.group(1).strip()
        m_city = re.search(r'所在城市[：:]\s*(\S+)', content)
        if m_city:
            info["city"] = m_city.group(1).strip()
        m_pos = re.search(r'意向岗位[：:]\s*(\S+)', content)
        if m_pos:
            info["position"] = m_pos.group(1).strip()
        tags = re.findall(r'核心标签\d+[：:]\s*(\S+)', content)
        if tags:
            info["tags"] = tags
    except Exception:
        pass
    return info

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Per-role LLM config (admin panel → DB → runtime) ──
    ADMIN_API_KEY: str = ""
    ADMIN_LLM_PROVIDER: str = "LongCat"
    ADMIN_LLM_MODEL: str = "LongCat-2.0-Preview"

    VISITOR_API_KEY: str = ""
    VISITOR_LLM_PROVIDER: str = "DeepSeek"
    VISITOR_LLM_MODEL: str = "deepseek-v4-flash"

    # ── Embedding (shared, SiliconFlow only) ──
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_API_BASE: str = "https://api.siliconflow.cn/v1"
    SILICONFLOW_EMBEDDING_MODEL: str = "BAAI/bge-m3"

    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    VISITOR_PASSWORD: str = "AGENTAGENT"

    MAX_SESSIONS: int = 10
    SESSION_TIMEOUT_MINUTES: int = 120
    SECRET_KEY: str = "answer-agent-secret-key-2026"
    RESUME_SHOW: bool = False
    PORTFOLIO_SHOW: bool = False
    TAVILY_API_KEY: str = ""
    FIRECRAWL_API_KEY: str = ""
    FIRECRAWL_DAILY_BUDGET: int = 20
    ANYSEARCH_API_KEY: str = ""
    AMAP_API_KEY: str = ""
    VISITOR_TAVILY_API_KEY: str = ""
    VISITOR_AMAP_API_KEY: str = ""

    KNOWLEDGE_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge")
    USER_DATA_DIR: str = os.path.join(os.path.dirname(__file__), "..", "user_data")
    VECTOR_STORE_DIR: str = os.path.join(os.path.dirname(__file__), "..", "vector_store")
    RESUME_DIR: str = os.path.join(os.path.dirname(__file__), "..", "resumes")
    DATABASE_PATH: str = os.path.join(os.path.dirname(__file__), "data", "app.db")
    APPENDIX_KNOWLEDGE_DIRS: str = "[]"
    CHROMIUM_PATH: str = "/usr/bin/chromium"

    AGENT_PROMPT: str = ""

    VISITOR_PROMPT_VERSION: int = 1
    VISITOR_SYSTEM_PROMPT_TEMPLATE: str = "你是{candidate_name}，正在和HR对话。用第一人称'我'自然交流。可用面试时间段：{schedule_info}"

    WELCOME_GREETING: str = "您好，欢迎您到来"
    WELCOME_SELF_INTRO: str = ""
    WELCOME_QUICK_QUESTIONS: str = """离职原因是什么？
期望薪资是多少？
最快何时到岗？
意向城市和工作形式？
核心技能和工具经验？
有哪些典型项目案例？"""
    INITIAL_MESSAGE: str = ""

settings = Settings()
