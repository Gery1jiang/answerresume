from fastapi import APIRouter, Depends, HTTPException, Query, Header
from fastapi.security import HTTPBearer
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import jwt

from sqlalchemy.orm import Session as DBSession
from services.portfolio_service import portfolio_service
from services.html_builder import html_builder
from services.session_manager import session_manager
from services.database import get_db
from services.stats_service import record_event
from services.enums import EventType
from config import settings

router = APIRouter(prefix="/admin/portfolio", tags=["Portfolio"])
security = HTTPBearer()

def verify_token(credentials):
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id", "")
        if user_id:
            return user_id
        # Fallback: look up by username
        username = payload.get("sub", "")
        if username:
            from services.database import SessionLocal
            from services.models import User
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.username == username).first()
                if user:
                    return user.id
            finally:
                db.close()
        return username or ""
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

class ConfigUpdate(BaseModel):
    style: Optional[str] = None
    blocks_order: Optional[List[str]] = None
    blocks_hidden: Optional[List[str]] = None
    contact_enabled: Optional[Dict[str, bool]] = None
    chat_enabled: Optional[bool] = None
    chat_position: Optional[str] = None

@router.get("/config")
async def get_config(credentials=Depends(security)):
    user_id = verify_token(credentials)
    return portfolio_service.get_config(user_id=user_id)

@router.post("/config")
async def save_config(req: ConfigUpdate, credentials=Depends(security)):
    user_id = verify_token(credentials)
    data = {k: v for k, v in req.dict().items() if v is not None}
    return portfolio_service.save_config(data, user_id=user_id)

@router.get("/preview")
async def get_preview(credentials=Depends(security)):
    user_id = verify_token(credentials)
    config = portfolio_service.get_config(user_id=user_id)
    knowledge = portfolio_service.get_knowledge_data(user_id=user_id)
    return {"config": config, "knowledge": knowledge}

class ExportRequest(BaseModel):
    style: str = "editorial"


@router.post("/export")
async def export_html(req: ExportRequest, credentials=Depends(security)):
    user_id = verify_token(credentials)
    style = req.style
    config = portfolio_service.get_config(user_id=user_id)
    config["style"] = style
    knowledge = portfolio_service.get_knowledge_data(user_id=user_id)
    html = html_builder.generate_html(config, knowledge)
    return PlainTextResponse(content=html, media_type="text/html")

@router.get("/styles")
async def get_styles(credentials=Depends(security)):
    verify_token(credentials)
    return {
        "styles": [
            {"id": "editorial", "name": "杂志风", "description": "排版优先 · Playfair Display · 暖白底色"},
            {"id": "developer", "name": "工程师风", "description": "深色终端 · JetBrains Mono · 绿色点缀"},
            {"id": "creative", "name": "创意人风", "description": "作品驱动 · DM Sans · 黑白交替"},
            {"id": "personal", "name": "个人品牌风", "description": "叙事优先 · Lora+Inter · 奶油底色"},
        ]
    }

class RebuildRequest(BaseModel):
    user_id: str = ""

@router.post("/rebuild")
async def rebuild_portfolio(req: RebuildRequest = None, credentials=Depends(security)):
    user_id = verify_token(credentials)
    if req and req.user_id:
        user_id = req.user_id
    try:
        data = portfolio_service.rebuild(user_id=user_id)
        return {"status": "success", "message": "个人主页重构完成", "items": len(data.get("projects", {}).get("project_list", [])) + len(data.get("work_experience", {}).get("work_list", []))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重构失败: {str(e)}")

@router.get("/build-status")
async def get_build_status(target_user_id: str = Query("", alias="user_id"), credentials=Depends(security)):
    user_id = target_user_id or verify_token(credentials)
    return portfolio_service.get_build_status(user_id=user_id)

@router.get("/visitor-preview")
async def visitor_preview(
    style: str = Query("editorial", description="Theme style"),
    user_id: str = Query("", description="User ID to preview portfolio for"),
    x_session_id: str = Header(None, alias="X-Session-ID"),
    db: DBSession = Depends(get_db),
):
    if x_session_id:
        record_event(EventType.PORTFOLIO, x_session_id, db)
    # Resolve user_id from session if not provided
    if not user_id and x_session_id:
        user_id = session_manager.get_session_user_id(x_session_id)
    config = portfolio_service.get_config(user_id=user_id)
    config["style"] = style
    knowledge = portfolio_service.get_knowledge_data(user_id=user_id)
    html = html_builder.generate_html(config, knowledge)
    return PlainTextResponse(content=html, media_type="text/html")
