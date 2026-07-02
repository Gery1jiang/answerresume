"""Memory manager — sliding window with LLM-based summary compression."""

import logging
from typing import Callable
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)

_SUMMARIZE_PROMPT = """You are a conversation summarizer for an AI assistant. Condense the following conversation history into a concise summary (2-4 sentences). Focus on:

- Key information the user has provided about themselves (name, skills, experience, job preferences)
- Actions the assistant has taken (resume generated, search performed, knowledge base updated)
- Any decisions or preferences the user has expressed
- Unresolved requests or pending tasks

Keep only information relevant for continuing the conversation. Write in third person.

Conversation:
{text}"""


class MemoryManager:
    """Sliding window with LLM-based summary compression for long conversations."""

    def __init__(self, llm_factory: Callable, max_raw_turns: int = 6):
        """
        Args:
            llm_factory: A callable that returns a ChatOpenAI (or similar) instance.
                         Should be cheap/fast — summarization runs on every overflow.
            max_raw_turns: Number of most recent user+assistant pairs to keep verbatim.
                           Older turns are compressed into a summary.
        """
        self._llm_factory = llm_factory
        self.max_raw_turns = max_raw_turns

    def build_context(self, records: list) -> list[BaseMessage]:
        """Convert DB records to BaseMessage list, applying summary compression
        if the history exceeds max_raw_turns * 2 messages.

        Args:
            records: List of DB rows with .role, .content attributes.

        Returns:
            A list of BaseMessage suitable for the agent's message chain.
        """
        total = len(records)
        keep_count = self.max_raw_turns * 2

        if total <= keep_count:
            return self._to_messages(records)

        # Split: older part gets summarized, recent part stays verbatim
        older = records[:total - keep_count]
        recent = records[total - keep_count:]

        summary = self._summarize(older)
        messages = [SystemMessage(content=f"【历史摘要】{summary}")]
        messages.extend(self._to_messages(recent))
        return messages

    def _summarize(self, records: list) -> str:
        """Summarize a list of conversation records using LLM, with fallback."""
        text_parts = []
        for r in records:
            role = "用户" if getattr(r, "role", "") == "user" else "助手"
            content = (getattr(r, "content", "") or "")[:500]
            text_parts.append(f"{role}: {content}")
        text = "\n".join(text_parts)

        if not text.strip():
            return ""

        # Truncate input to avoid overflowing context
        if len(text) > 6000:
            text = text[-6000:]

        try:
            llm = self._llm_factory()
            response = llm.invoke(
                _SUMMARIZE_PROMPT.format(text=text),
                timeout=30,
            )
            result = (getattr(response, "content", None) or "").strip()
            if result:
                return result
        except Exception as e:
            logger.warning(f"[memory] LLM summarization failed: {e}")

        # Fallback: simple concatenation of last few messages
        return self._fallback_summary(records)

    @staticmethod
    def _fallback_summary(records: list) -> str:
        parts = []
        for r in records[-6:]:
            role = "用户" if getattr(r, "role", "") == "user" else "助手"
            content = (getattr(r, "content", "") or "")[:150]
            parts.append(f"{role}: {content}")
        summary = " | ".join(parts)
        if len(summary) > 2000:
            summary = summary[:2000] + "..."
        return summary

    @staticmethod
    def _to_messages(records: list) -> list[BaseMessage]:
        messages: list[BaseMessage] = []
        for r in records:
            content = getattr(r, "content", "") or ""
            if content and len(content) > 4000:
                content = content[:4000] + "\n...（截断）"
            role = getattr(r, "role", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        return messages
