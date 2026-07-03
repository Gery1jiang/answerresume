"""RAG worker — wraps rag_service as HTTP microservice.

Endpoints:
  GET  /health
  POST /rag/init-qa           — init QA chain for a user
  POST /rag/rebuild-vector    — rebuild vector store for a user
  POST /rag/clear-cache       — clear all caches
  POST /rag/answer            — non-streaming answer (for health check / sync calls)
"""

import os
import json
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    stream=os.sys.stdout,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("rag_worker")

app = FastAPI(title="RAG Worker", version="1.0.0")

# ── Lazy import to avoid heavy deps blocking startup ──
_rag_service = None


def _get_rag():
    global _rag_service
    if _rag_service is None:
        from services.rag_service import rag_service
        _rag_service = rag_service
    return _rag_service


class InitQARequest(BaseModel):
    user_id: str = ""


class RebuildRequest(BaseModel):
    user_id: Optional[str] = None


class AnswerRequest(BaseModel):
    question: str
    conversation_history: str = ""
    use_visitor_llm: bool = True
    user_id: str = ""


class AnswerStreamRequest(BaseModel):
    question: str
    conversation_history: str = ""
    use_visitor_llm: bool = True
    user_id: str = ""


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/rag/init-qa")
async def api_init_qa(req: InitQARequest):
    try:
        rag = _get_rag()
        ok = rag.init_qa_chain(user_id=req.user_id or None)
        return {"ok": ok}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/rag/rebuild-vector")
async def api_rebuild_vector(req: RebuildRequest):
    try:
        rag = _get_rag()
        from services.database import SessionLocal
        db = SessionLocal()
        try:
            rag.build_main_with_mapping(db, user_id=req.user_id)
        finally:
            db.close()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/rag/clear-cache")
async def api_clear_cache():
    try:
        rag = _get_rag()
        rag.clear_cache()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/rag/answer")
async def api_answer(req: AnswerRequest):
    try:
        rag = _get_rag()
        chunks = []
        async for chunk in rag.answer_stream(
            question=req.question,
            conversation_history=req.conversation_history,
            use_visitor_llm=req.use_visitor_llm,
            user_id=req.user_id,
        ):
            chunks.append(chunk)
        return {"answer": "".join(chunks)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/rag/answer-stream")
async def api_answer_stream(req: AnswerStreamRequest):
    rag = _get_rag()

    async def event_stream():
        try:
            async for chunk in rag.answer_stream(
                question=req.question,
                conversation_history=req.conversation_history,
                use_visitor_llm=req.use_visitor_llm,
                user_id=req.user_id,
            ):
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
