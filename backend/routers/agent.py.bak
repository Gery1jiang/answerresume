import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from services.agent_service import run_agent, stream_agent_events, clear_history, clear_all_history, get_history, get_task, get_events, cancel_running_task
from services.database import SessionLocal
from services.models.agent_event import AgentEvent
from schemas.admin_schemas import MessageResponse
from services.prompt_injection import check_message
from routers.deps import get_current_user
from services.models import User

router = APIRouter(prefix="/admin/agent", tags=["Agent"])

MAX_FILE_CHARS = 15000


def _apply_file_context(user_message: str, file_ids: list[str]) -> str:
    if not file_ids:
        return user_message
    markers = "\n".join(f"[文件: {fid}]" for fid in file_ids)
    return f"{markers}\n\n{user_message}"


class AgentChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    file_ids: list[str] = []


class AgentChatResponse(BaseModel):
    response: str
    steps: list
    resume_id: Optional[int] = None


class UploadResponse(BaseModel):
    file_id: str
    file_name: str
    file_type: str
    file_size: int


class ClearRequest(BaseModel):
    session_id: str


class HistoryMessageResponse(BaseModel):
    role: str
    content: str
    resume_id: Optional[int] = None
    guide_id: Optional[int] = None
    created_at: Optional[str] = None


class HistoryResponse(BaseModel):
    messages: list[HistoryMessageResponse]


class TaskStatusResponse(BaseModel):
    status: str
    response: Optional[str] = None
    resume_id: Optional[int] = None
    request: Optional[str] = None


class AgentEventResponse(BaseModel):
    type: str
    data: dict
    sequence: int
    created_at: Optional[str] = None


class AgentEventsListResponse(BaseModel):
    events: list[AgentEventResponse]


class ConfirmToolRequest(BaseModel):
    confirm_id: str
    confirmed: bool


@router.post("/confirm-tool")
async def confirm_tool(req: ConfirmToolRequest, user: User = Depends(get_current_user)):
    from datetime import datetime
    # Find the original tool_call event to get session_id and task_id
    db = SessionLocal()
    try:
        evt = db.query(AgentEvent).filter(
            AgentEvent.event_type == "tool_call",
            AgentEvent.event_data.contains(req.confirm_id),
        ).order_by(AgentEvent.created_at.desc()).first()
        if not evt:
            return {"status": "expired", "message": "确认请求已过期或不存在"}
        # Save confirmation result
        max_seq = db.query(AgentEvent).filter(
            AgentEvent.session_id == evt.session_id,
            AgentEvent.task_id == evt.task_id,
        ).order_by(AgentEvent.sequence.desc()).first()
        next_seq = (max_seq.sequence + 1) if max_seq else 0
        result_event = AgentEvent(
            session_id=evt.session_id,
            task_id=evt.task_id,
            event_type="tool_confirm_result",
            event_data=json.dumps({"confirm_id": req.confirm_id, "confirmed": req.confirmed}),
            sequence=next_seq,
            created_at=datetime.utcnow(),
        )
        db.add(result_event)
        db.commit()
        return {"status": "ok", "confirmed": req.confirmed}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@router.post("/upload", response_model=UploadResponse)
async def agent_upload(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    from services.document_parser import is_supported
    if not is_supported(file.filename):
        raise HTTPException(status_code=400,
                            detail=f"不支持的文件格式: {file.filename}。支持的格式: 图片/PDF/DOCX/MD/PPTX/XLSX/HTML")

    content = await file.read()
    from services.container import Container
    with Container(user.id) as c:
        result = c.file_service.save_upload(user.id, file.filename, content)

    from core.events import event_bus, EventType
    event_bus.emit(EventType.FILE_UPLOADED, {
        "file_id": result["file_id"],
        "file_name": result["file_name"],
        "file_type": result["file_type"],
        "file_size": result["file_size"],
    }, user_id=user.id)

    return UploadResponse(
        file_id=result["file_id"],
        file_name=result["file_name"],
        file_type=result["file_type"],
        file_size=result["file_size"],
    )


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(req: AgentChatRequest, user: User = Depends(get_current_user)):
    is_safe, reason = check_message(req.message)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"消息内容被拒绝：{reason}")

    try:
        session_id = req.session_id or f"agent_{user.id}"
        message = _apply_file_context(req.message, req.file_ids)
        result = run_agent(session_id, message, user_id=user.id)
        return AgentChatResponse(
            response=result["response"],
            steps=result["steps"],
            resume_id=result.get("resume_id"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent调用失败: {str(e)}")


@router.post("/chat/stream")
async def agent_chat_stream(req: AgentChatRequest, user: User = Depends(get_current_user)):
    is_safe, reason = check_message(req.message)
    if not is_safe:
        async def error_gen():
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': reason}}, ensure_ascii=False)}\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")

    session_id = req.session_id or f"agent_{user.id}"
    message = _apply_file_context(req.message, req.file_ids)

    async def event_generator():
        try:
            yield f"data: {json.dumps({'type': 'status', 'data': {'message': '思考中...'}}, ensure_ascii=False)}\n\n"
            async for event in stream_agent_events(session_id, message, user_id=user.id):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history", response_model=HistoryResponse)
async def agent_history(session_id: str = "", user: User = Depends(get_current_user)):
    sid = session_id or f"agent_{user.id}"
    messages = get_history(sid, user_id=user.id)
    return HistoryResponse(messages=messages)


@router.get("/task-status", response_model=TaskStatusResponse)
async def agent_task_status(session_id: str = "", user: User = Depends(get_current_user)):
    sid = session_id or f"agent_{user.id}"
    task = get_task(sid, user_id=user.id)
    if task is None:
        return TaskStatusResponse(status="none")
    return TaskStatusResponse(
        status=task["status"],
        response=task.get("response"),
        resume_id=task.get("resume_id"),
        request=task.get("request"),
    )


@router.get("/events", response_model=AgentEventsListResponse)
async def agent_events(session_id: str = "", user: User = Depends(get_current_user)):
    sid = session_id or f"agent_{user.id}"
    events = get_events(sid, user_id=user.id)
    return AgentEventsListResponse(events=events)


@router.post("/clear", response_model=MessageResponse)
async def agent_clear(req: ClearRequest, user: User = Depends(get_current_user)):
    try:
        clear_history(req.session_id, user_id=user.id)
        return MessageResponse(message="对话历史已清空")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空失败: {str(e)}")


@router.post("/cancel")
async def agent_cancel(req: ClearRequest, user: User = Depends(get_current_user)):
    ok = cancel_running_task(req.session_id, user_id=user.id)
    if ok:
        return {"status": "cancelled", "message": "任务已取消"}
    return {"status": "ok", "message": "没有运行中的任务"}


@router.post("/clear-all", response_model=MessageResponse)
async def agent_clear_all(user: User = Depends(get_current_user)):
    try:
        clear_all_history(user_id=user.id)
        return MessageResponse(message="所有Agent对话历史已清空")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空失败: {str(e)}")
