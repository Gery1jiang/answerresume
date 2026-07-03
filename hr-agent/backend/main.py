from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import asyncio
import json
import os

from config import settings
from services.database import init_db
from services.session_manager import session_manager
from services.rag_service import rag_service
from services.ai_service import generate_resume_json
from services.pdf_service import generate_pdf_sync
from schemas.resume_schemas import ResumeGenerateRequest, PDFExportRequest
from routers import visitor, admin, agent, portfolio, prompts_admin, auth, usage

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    
    # Load ALL persisted config from DB into runtime settings
    # (so admin panel changes survive container restart)
    try:
        from services.database import SessionLocal
        from services.repository.container import RepoContainer
        db = SessionLocal()
        cfg = RepoContainer(db).app_config.get_data_dict("app_config")
        if cfg:
            # Admin LLM config
            if cfg.get("llm_provider"):
                settings.ADMIN_LLM_PROVIDER = cfg["llm_provider"]
            if cfg.get("llm_model"):
                settings.ADMIN_LLM_MODEL = cfg["llm_model"]
            if cfg.get("llm_api_key"):
                settings.ADMIN_API_KEY = cfg["llm_api_key"]
            # Visitor LLM config
            if cfg.get("visitor_llm_api_key"):
                settings.VISITOR_API_KEY = cfg["visitor_llm_api_key"]
            if cfg.get("visitor_llm_provider"):
                settings.VISITOR_LLM_PROVIDER = cfg["visitor_llm_provider"]
            if cfg.get("visitor_llm_model"):
                settings.VISITOR_LLM_MODEL = cfg["visitor_llm_model"]
            # Other config
            if cfg.get("visitor_password"):
                settings.VISITOR_PASSWORD = cfg["visitor_password"]
            if cfg.get("max_sessions"):
                settings.MAX_SESSIONS = cfg["max_sessions"]
            if cfg.get("session_timeout_minutes"):
                settings.SESSION_TIMEOUT_MINUTES = cfg["session_timeout_minutes"]
            if cfg.get("resume_show") is not None:
                settings.RESUME_SHOW = cfg["resume_show"]
            if cfg.get("appendix_knowledge_dir"):
                settings.APPENDIX_KNOWLEDGE_DIR = cfg["appendix_knowledge_dir"]
            # Search API Keys
            for _key in ("tavily_api_key", "firecrawl_api_key", "anysearch_api_key",
                         "amap_api_key", "visitor_tavily_api_key", "visitor_amap_api_key"):
                if cfg.get(_key):
                    setattr(settings, _key.upper(), cfg[_key])
        db.close()
    except Exception as e:
        print(f"[startup] Failed to load app_config: {e}", flush=True)
    
    try:
        rag_service.init_qa_chain()
    except Exception as e:
        print(f"[startup] Failed to init QA chain: {e}", flush=True)

    # Seed prompts from seed_prompts.py (compares hash, creates versions for changes)
    try:
        from services.seed_prompts import PROMPT_DEFAULTS
        from services.prompt_manager import prompt_manager
        count = prompt_manager.seed_defaults(PROMPT_DEFAULTS)
        if count > 0:
            print(f"[startup] Seeded {count} prompt(s) (new or updated)", flush=True)
    except Exception as e:
        print(f"[startup] Failed to seed prompts: {e}", flush=True)
    
    try:
        import core.handlers  # noqa: F401 — register EventBus handlers
        print("[startup] EventBus handlers registered", flush=True)
    except Exception as e:
        print(f"[startup] Failed to register EventBus handlers: {e}", flush=True)

    asyncio.create_task(cleanup_task())
    yield

async def cleanup_task():
    while True:
        await asyncio.sleep(300)
        session_manager.cleanup_expired_sessions()

app = FastAPI(
    title="Answer Agent Backend",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 确保上传目录存在
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "uploads")
os.makedirs(os.path.join(UPLOAD_DIR, "qrcodes"), exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.include_router(auth.router)
app.include_router(visitor.router)
app.include_router(admin.router)
app.include_router(agent.router)
app.include_router(portfolio.router)
app.include_router(prompts_admin.router)
app.include_router(usage.router)

@app.get("/")
async def root():
    return {"message": "Answer Agent Backend is running", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/api/generate-resume")
async def api_generate_resume(req: ResumeGenerateRequest):
    try:
        resume_data = generate_resume_json(req.raw_text, req.target_job)
        return {"status": "success", "data": resume_data}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/api/export-pdf")
async def api_export_pdf(req: PDFExportRequest):
    try:
        from services.pdf_service import _generate_pdf_async
        full_html = req.html
        if req.css:
            full_html = '<!DOCTYPE html>\n<html><head><meta charset=\"UTF-8\"><style>' + req.css + '</style></head>\n<body>' + req.html + '</body>\n</html>'
        pdf_bytes = await _generate_pdf_async(full_html)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=resume.pdf"}
        )
    except Exception as e:
        return {"status": "error", "detail": str(e)}
