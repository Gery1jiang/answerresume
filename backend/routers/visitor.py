import asyncio
from fastapi import APIRouter, Depends, HTTPException, Header, Request, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel, Field
from typing import Optional
from config import settings, get_candidate_name, get_candidate_profile
from services.database import get_db, SessionLocal
from services.models import Conversation, InterviewGuide
from services.session_manager import session_manager
from services.stats_service import record_event
from services.enums import EventType
from services.rag_service import rag_service
from services.resume_service import resume_service
from services.portfolio_service import portfolio_service
from services.intent_detector import classify_intent
from datetime import datetime
import os
import json


def _save_conversation(session_id: str, role: str, content: str, user_id: str = ""):
    if not content:
        return
    from services.repository.container import RepoContainer
    db = SessionLocal()
    try:
        RepoContainer(db).conversation.create(
            session_id=session_id,
            role=role,
            content=content.strip(),
            user_id=user_id or session_id,
        )
    except Exception:
        pass
    finally:
        db.close()

async def _check_and_save_intent(session_id: str, conversation_history: list):
    """Check intent and store suggestion in session if booking should be offered."""
    from services.repository.container import RepoContainer
    db = SessionLocal()
    try:
        existing = RepoContainer(db).interview_guide.get_by_session_id(session_id)
        if existing and existing.source == "visitor":
            return
        result = await classify_intent(conversation_history)
        if result.get("should_suggest_booking"):
            session_manager.set_booking_suggestion(
                session_id,
                result.get("intent", "interview_interest"),
                booking_time=result.get("suggested_time"),
            )
    except Exception as e:
        print(f"Intent check failed: {e}")
    finally:
        db.close()


router = APIRouter(prefix="/api", tags=["visitor"])

class VerifyPasswordRequest(BaseModel):
    password: str
    client_ip: str
    user_id: str = ""

class ChatRequest(BaseModel):
    message: str = Field(..., max_length=2000)

class VerifyPasswordResponse(BaseModel):
    session_id: str
    anonymous_id: str

class BookingSuggestionResponse(BaseModel):
    suggest_booking: bool
    booking_intent: str | None = None
    booking_time: str | None = None

class SubmitBookingResponse(BaseModel):
    message: str
    guide_id: int
    status: str

class DismissBookingResponse(BaseModel):
    ok: bool

class CheckSessionResponse(BaseModel):
    valid: bool

class ResumeStatusResponse(BaseModel):
    resume_show: bool

class ProfileResponse(BaseModel):
    name: str = ""
    city: str = ""
    position: str = ""
    tags: list[str] = []

class WelcomeConfigResponse(BaseModel):
    greeting: str = ""
    self_intro: str = ""
    initial_message: str = ""
    quick_questions: list[str] = []
    resume_show: bool = False
    portfolio_show: bool = False

class PublicConfigResponse(BaseModel):
    """Public (non-sensitive) config exposed to visitor-facing services."""
    amap_api_key: str = ""

class ResumePreviewResponse(BaseModel):
    html: str
    css: str
    content: str

class VisitorStatusResponse(BaseModel):
    enabled: bool
    user_name: str = ""
    has_password: bool = False

class UserByUsernameResponse(BaseModel):
    exists: bool
    user_id: str = ""
    username: str = ""

@router.get("/user-by-username/{username}", response_model=UserByUsernameResponse)
async def user_by_username(username: str, db: DBSession = Depends(get_db)):
    """Look up a user by username. Public endpoint for visitor URL routing."""
    from services.repository.container import RepoContainer
    user = RepoContainer(db).user.get_by_username(username)
    if not user:
        return UserByUsernameResponse(exists=False)
    return UserByUsernameResponse(exists=True, user_id=user.id, username=user.username)


@router.get("/visitor-status", response_model=VisitorStatusResponse)
async def visitor_status(user_id: str = "", db: DBSession = Depends(get_db)):
    """Check if a user has visitor access enabled. Public endpoint."""
    if not user_id or not str(user_id).strip():
        # Legacy mode: check global visitor password availability
        from config import settings as cfg
        has_pwd = bool(cfg.VISITOR_PASSWORD)
        return VisitorStatusResponse(enabled=has_pwd)
    from services.repository.container import RepoContainer
    repo = RepoContainer(db)
    enabled_cfg = repo.user_config.get_by_key(str(user_id), "visitor_enabled")
    pwd_cfg = repo.user_config.get_by_key(str(user_id), "visitor_password")
    user = repo.user.get_by_id(str(user_id))
    enabled = enabled_cfg is not None and enabled_cfg.config_value == "true"
    has_password = bool(pwd_cfg and pwd_cfg.config_value)
    if not enabled:
        return VisitorStatusResponse(enabled=False)
    return VisitorStatusResponse(enabled=True, has_password=has_password, user_name=user.username if user else "")

@router.post("/verify-password", response_model=VerifyPasswordResponse)
async def verify_password(req: VerifyPasswordRequest, db: DBSession = Depends(get_db)):
    if session_manager.check_ip_locked(req.client_ip):
        raise HTTPException(status_code=429, detail="访问次数过多，请10分钟后再试")

    # Per-user password check
    if req.user_id and str(req.user_id).strip():
        from services.repository.container import RepoContainer
        repo = RepoContainer(db)
        enabled_cfg = repo.user_config.get_by_key(str(req.user_id), "visitor_enabled")
        if not enabled_cfg or enabled_cfg.config_value != "true":
            raise HTTPException(status_code=403, detail="该用户的访客访问未开启")
        pwd_cfg = repo.user_config.get_by_key(str(req.user_id), "visitor_password")
        expected_pwd = pwd_cfg.config_value if pwd_cfg else ""
        if req.password != expected_pwd:
            session_manager.record_failed_attempt(req.client_ip)
            raise HTTPException(status_code=401, detail="访问口令无效，请核对后重新输入")
    else:
        # Global password (legacy)
        from services.repository.container import RepoContainer
        repo = RepoContainer(db)
        _db_cfg = repo.app_config.get_data_dict("app_config")
        _expected_pwd = _db_cfg.get("visitor_password", settings.VISITOR_PASSWORD)

        if req.password != _expected_pwd:
            session_manager.record_failed_attempt(req.client_ip)
            raise HTTPException(status_code=401, detail="访问口令无效，请核对后重新输入")

    session_manager.clear_failed_attempts(req.client_ip)

    if session_manager.get_active_count() >= settings.MAX_SESSIONS:
        raise HTTPException(status_code=503, detail="当前访问人数较多，请稍后再试")

    uid = req.user_id if req.user_id and str(req.user_id).strip() else ""
    session_id = session_manager.create_session(db, user_id=uid)
    anonymous_id = f"访客_{session_id[:8]}"

    record_event(EventType.VISIT, session_id, db, uid)

    return VerifyPasswordResponse(session_id=session_id, anonymous_id=anonymous_id)

@router.post("/chat")
async def chat(
    message: ChatRequest,
    x_session_id: Optional[str] = Header(None),
    db: DBSession = Depends(get_db)
):
    if not x_session_id or not session_manager.validate_session(x_session_id):
        raise HTTPException(status_code=401, detail="会话无效或已过期，请刷新页面")

    uid = session_manager.get_session_user_id(x_session_id)
    session_manager.refresh_session(x_session_id)
    record_event(EventType.CHAT, x_session_id, db, uid)

    # 先获取历史（不包含当前消息），让LLM更快开始响应
    history = session_manager.get_conversation_history(db, x_session_id)
    context = session_manager.build_context_from_history(history)

    ai_response = []
    intent_detection_task = None

    async def generate():
        nonlocal ai_response, intent_detection_task
        try:
            asyncio.create_task(
                asyncio.to_thread(_save_conversation, x_session_id, "user", message.message, uid)
            )
            try:
                async for chunk in rag_service.answer_stream(message.message, context, use_visitor_llm=True, user_id=uid):
                    ai_response.append(chunk)
                    yield chunk
            except Exception as e:
                err_msg = f"回答失败: {type(e).__name__}"
                print(f"[visitor] stream error: {type(e).__name__}: {e}")
                # Yield error as response text so the client gets a complete response
                ai_response.append(err_msg)
                yield err_msg
            # Application-level end-of-stream marker
            yield '__STREAM_END__'
        finally:
            if ai_response:
                full_response = "".join(ai_response)
                asyncio.create_task(
                    asyncio.to_thread(_save_conversation, x_session_id, "ai", full_response, uid)
                )
                # Run intent detection after response is saved — does not block the stream
                conversation_for_intent = history + [
                    {"role": "user", "content": message.message},
                    {"role": "assistant", "content": full_response},
                ]
                intent_detection_task = asyncio.create_task(
                    _check_and_save_intent(x_session_id, conversation_for_intent)
                )

    return StreamingResponse(
        generate(), media_type="text/plain",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}
    )

@router.get("/booking-suggestion", response_model=BookingSuggestionResponse)
async def get_booking_suggestion(
    x_session_id: Optional[str] = Header(None),
    db: DBSession = Depends(get_db)
):
    if not x_session_id or not session_manager.validate_session(x_session_id):
        raise HTTPException(status_code=401, detail="会话无效或已过期，请刷新页面")
    suggestion = session_manager.get_booking_suggestion(x_session_id)
    if suggestion:
        return suggestion
    return {"suggest_booking": False, "booking_intent": None}

class BookingRequest(BaseModel):
    session_id: str
    company_name: str = Field(..., min_length=1)
    job_title: str = Field(..., min_length=1)
    hr_name: str = ""
    hr_phone: str = ""
    hr_email: str = Field(..., min_length=1)
    interview_address: str = ""
    interview_time: str = Field(..., min_length=1)
    interview_address_lng: Optional[float] = None
    interview_address_lat: Optional[float] = None

@router.post("/booking", response_model=SubmitBookingResponse)
async def submit_booking(
    data: BookingRequest,
    background_tasks: BackgroundTasks,
    db: DBSession = Depends(get_db)
):
    if not data.session_id or not session_manager.validate_session(data.session_id):
        raise HTTPException(status_code=401, detail="会话无效或已过期")
    try:
        interview_time = datetime.fromisoformat(data.interview_time.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="面试时间格式错误")

    # 同 session 编辑而非重复新增
    from services.repository.container import RepoContainer
    repo = RepoContainer(db)
    existing = repo.interview_guide.get_by_session_id(data.session_id)

    if existing:
        existing.company_name = data.company_name
        existing.job_title = data.job_title
        existing.hr_name = data.hr_name
        existing.hr_phone = data.hr_phone
        existing.hr_email = data.hr_email
        existing.interview_address = data.interview_address
        existing.interview_address_lng = data.interview_address_lng
        existing.interview_address_lat = data.interview_address_lat
        existing.interview_time = interview_time
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        guide = existing
    else:
        uid = session_manager.get_session_user_id(data.session_id)
        guide = repo.interview_guide.create(
            company_name=data.company_name,
            job_title=data.job_title,
            hr_name=data.hr_name,
            hr_phone=data.hr_phone,
            hr_email=data.hr_email,
            interview_address=data.interview_address,
            interview_address_lng=data.interview_address_lng,
            interview_address_lat=data.interview_address_lat,
            interview_time=interview_time,
            status="pending",
            source="visitor",
            session_id=data.session_id,
            user_id=uid,
        )

    session_manager.clear_booking_suggestion(data.session_id)
    return {
        "message": "邀约安排已提交",
        "guide_id": guide.id,
        "status": "pending",
    }


@router.get("/booking/{session_id}")
async def get_booking(session_id: str, db: DBSession = Depends(get_db)):
    from services.repository.container import RepoContainer
    guide = RepoContainer(db).interview_guide.get_by_session_id(session_id)
    if guide:
        return {
            "guide_id": guide.id,
            "status": guide.status,
            "company_name": guide.company_name,
            "job_title": guide.job_title,
            "hr_name": guide.hr_name or "",
            "hr_phone": guide.hr_phone or "",
            "hr_email": guide.hr_email or "",
            "interview_address": guide.interview_address or "",
            "interview_time": guide.interview_time.isoformat() if guide.interview_time else "",
        }
    return {"guide_id": 0, "status": "none"}

class BookingDismissRequest(BaseModel):
    session_id: str

@router.post("/booking-dismiss", response_model=DismissBookingResponse)
async def dismiss_booking_suggestion(data: BookingDismissRequest):
    if not data.session_id or not session_manager.validate_session(data.session_id):
        raise HTTPException(status_code=401, detail="会话无效或已过期")
    session_manager.clear_booking_suggestion(data.session_id)
    return {"ok": True}

@router.get("/resume/download")
async def download_resume(
    x_session_id: Optional[str] = Header(None),
    db: DBSession = Depends(get_db)
):
    if not x_session_id or not session_manager.validate_session(x_session_id):
        raise HTTPException(status_code=401, detail="会话无效或已过期，请刷新页面")

    if not settings.RESUME_SHOW:
        raise HTTPException(status_code=403, detail="简历暂未开放")

    try:
        uid = session_manager.get_session_user_id(x_session_id)
        resume = resume_service.get_default_resume(user_id=uid)
        if not resume:
            raise HTTPException(status_code=404, detail="暂无默认简历，请联系求职者")
        
        if uid:
            filepath = os.path.join(settings.USER_DATA_DIR, str(uid), "resumes", resume.filename)
        else:
            filepath = os.path.join(settings.RESUME_DIR, resume.filename)
        if not os.path.exists(filepath):
            filepath = os.path.join(settings.RESUME_DIR, resume.filename)
        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="简历文件不存在")
        
        record_event(EventType.DOWNLOAD, x_session_id, db, uid)

        resume_data = json.loads(resume.content) if resume.content else {}
        personal = resume_data.get("personal", {})
        name = personal.get("name", "")
        phone = personal.get("phone", "")
        job_title = personal.get("jobTitle", "")
        parts = [p for p in [name, job_title, phone] if p]
        filename = "_".join(parts) + ".pdf" if parts else "resume.pdf"

        from fastapi.responses import Response
        from urllib.parse import quote
        with open(filepath, "rb") as f:
            pdf_bytes = f.read()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
                "Content-Length": str(len(pdf_bytes)),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取简历失败: {str(e)}")

@router.get("/profile", response_model=ProfileResponse)
async def get_profile():
    return get_candidate_profile()

@router.get("/resume/status", response_model=ResumeStatusResponse)
async def get_resume_status():
    return {"resume_show": settings.RESUME_SHOW}


@router.get("/check-session", response_model=CheckSessionResponse)
async def check_session(x_session_id: Optional[str] = Header(None)):
    if not x_session_id or not session_manager.validate_session(x_session_id):
        raise HTTPException(status_code=401, detail="会话无效或已过期，请刷新页面")
    return {"valid": True}

def _get_user_display_name(user_id: str) -> str:
    """Get user's display name (display_name > personal_info.name > username)."""
    try:
        from services.repository.container import RepoContainer
        from services.database import SessionLocal
        db = SessionLocal()
        try:
            user = RepoContainer(db).user.get_by_id(user_id)
            if user:
                return user.display_name or user.username
        finally:
            db.close()
    except Exception:
        pass
    return ""

def _session_user_id(x_session_id: Optional[str] = Header(None)) -> str:
    """Extract user_id from session."""
    if not x_session_id or not session_manager.validate_session(x_session_id):
        return ""
    return session_manager.get_session_user_id(x_session_id)


@router.get("/welcome-config", response_model=WelcomeConfigResponse)
async def get_welcome_config(x_session_id: Optional[str] = Header(None)):
    uid = _session_user_id(x_session_id)
    from services.database import SessionLocal
    from services.repository.container import RepoContainer

    # Get user-specific welcome config
    db_cfg = {}
    name = ""
    try:
        db = SessionLocal()
        repo = RepoContainer(db)
        if uid:
            db_cfg = repo.knowledge_base.get_data_dict(uid, "welcome_config")
            user = repo.user.get_by_id(uid)
            if user:
                name = user.display_name or user.username
        else:
            # Fallback: global config (legacy)
            db_cfg = repo.knowledge_base.get_data_dict("", "welcome_config")
        db.close()
    except Exception:
        pass

    if not name:
        # Try to get the user's real name from their personal_info in DB
        name = _get_user_display_name(uid) if uid else get_candidate_name()
    if not name:
        name = get_candidate_name()

    # Get user's actual FAQ questions from DB
    faq_questions = []
    try:
        db2 = SessionLocal()
        repo2 = RepoContainer(db2)
        faq_row = repo2.knowledge_base.get_by_category(uid, "faq") if uid else None
        if faq_row and faq_row.data:
            faq_data = json.loads(faq_row.data)
            faq_questions = [item["question"] for item in faq_data.get("faq_list", []) if item.get("question")][:6]
        else:
            # Fallback to seed questions from admin.py
            from routers.admin import FAQ_QUESTIONS_SEED
            faq_questions = [item["question"] for item in FAQ_QUESTIONS_SEED if item.get("question")][:6]
        db2.close()
    except Exception:
        pass

    if uid and not db_cfg:
        greeting = "您好，欢迎您的到来"
        self_intro = f"我叫{name}，正在寻找新的职业机会。"
        initial_msg = f"您好，我是{name}，您想了解我的哪些方面？"
        questions = faq_questions
    else:
        greeting = db_cfg.get("greeting", settings.WELCOME_GREETING)
        self_intro = db_cfg.get("self_intro", settings.WELCOME_SELF_INTRO) or f"我叫{name}，正在寻找新的职业机会。"
        initial_msg = db_cfg.get("initial_message", settings.INITIAL_MESSAGE) or f"您好，我是{name}，正在看新的工作机会。您想了解我的哪些方面？"
        questions_raw = db_cfg.get("quick_questions", "")
        if questions_raw:
            questions = questions_raw.split("\n")
        else:
            questions = faq_questions
    return {
        "greeting": greeting,
        "self_intro": self_intro,
        "initial_message": initial_msg,
        "quick_questions": [q for q in questions if q.strip()],
        "resume_show": settings.RESUME_SHOW,
        "portfolio_show": portfolio_service.get_config(user_id=uid).get("portfolio_show", False) if uid else False
    }

@router.get("/resume/preview", response_model=ResumePreviewResponse)
async def preview_resume(
    x_session_id: Optional[str] = Header(None),
    db: DBSession = Depends(get_db)
):
    if not x_session_id or not session_manager.validate_session(x_session_id):
        raise HTTPException(status_code=401, detail="会话无效或已过期，请刷新页面")

    if not settings.RESUME_SHOW:
        raise HTTPException(status_code=403, detail="简历暂未开放")

    try:
        uid = session_manager.get_session_user_id(x_session_id)
        resume = resume_service.get_default_resume(user_id=uid)
        if not resume:
            raise HTTPException(status_code=404, detail="暂无默认简历，请联系求职者")
        
        record_event(EventType.PREVIEW, x_session_id, db, uid)
        
        from services.resume_templates import render_resume as visitor_render
        import json as _vj
        try:
            _vd = _vj.loads(resume.content)
            _vtmpl = _vd.get("_template", "modern")
        except:
            _vtmpl = "modern"
        html_content = visitor_render(resume.content, _vtmpl)
        return {"html": html_content, "css": "", "content": resume.content}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取简历失败: {str(e)}")


@router.get("/public-config", response_model=PublicConfigResponse)
async def get_public_config():
    """Public config endpoint — no auth required, used by visitor Flask app."""
    return PublicConfigResponse(
        amap_api_key=getattr(settings, "VISITOR_AMAP_API_KEY", ""),
    )


class ExportPdfRequest(BaseModel):
    html: str
    css: str = ""

@router.post("/export-pdf")
async def export_pdf(
    req: ExportPdfRequest,
    x_session_id: Optional[str] = Header(None),
    db: DBSession = Depends(get_db)
):
    if not x_session_id or not session_manager.validate_session(x_session_id):
        raise HTTPException(status_code=401, detail="会话无效或已过期，请刷新页面")

    if not settings.RESUME_SHOW:
        raise HTTPException(status_code=403, detail="简历暂未开放")

    try:
        from services.pdf_service import _generate_pdf_async
        full_html = req.html
        if req.css:
            full_html = '<!DOCTYPE html>\n<html><head><meta charset=\"UTF-8\"><style>' + req.css + '</style></head>\n<body>' + req.html + '</body>\n</html>'
        pdf_bytes = await _generate_pdf_async(full_html)

        uid = session_manager.get_session_user_id(x_session_id)
        record_event(EventType.DOWNLOAD, x_session_id, db, uid)

        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=resume.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF生成失败: {str(e)}")
