"""RAG client — HTTP call to rag-worker only. Raises on failure."""

import os
import json
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

RAG_WORKER_URL = os.environ.get("RAG_WORKER_URL", "").strip()


async def rag_answer_stream(
    question: str,
    conversation_history: str = "",
    use_visitor_llm: bool = True,
    user_id: str = "",
) -> AsyncGenerator[str, None]:
    """Stream RAG answer via HTTP to rag-worker. Raises RuntimeError if URL not configured."""
    import httpx

    if not RAG_WORKER_URL:
        raise RuntimeError("RAG_WORKER_URL not configured")

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            f"{RAG_WORKER_URL}/rag/answer-stream",
            json={
                "question": question,
                "conversation_history": conversation_history,
                "use_visitor_llm": use_visitor_llm,
                "user_id": user_id,
            },
        ) as resp:
            if resp.status_code != 200:
                error_text = await resp.aread()
                logger.warning("rag-worker HTTP %s: %s", resp.status_code, error_text)
                raise RuntimeError(f"rag-worker returned {resp.status_code}")
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        payload = json.loads(data)
                        chunk = payload.get("chunk", "")
                        if chunk:
                            yield chunk
                    except json.JSONDecodeError:
                        continue
