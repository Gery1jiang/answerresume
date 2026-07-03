"""Intent rewriter — LLM is the single intent engine.

File marker (pure syntax) → LLM with conversation history → keyword fallback.
"""

import re

_FILE_MARKER = re.compile(r"\[文件:\s*(\S+\.\w+)\]")


def _extract_filenames(text: str) -> list[str]:
    return _FILE_MARKER.findall(text)


def _strip_file_content(text: str) -> str:
    close_tag = "[/上传文件内容]"
    if close_tag in text:
        idx = text.rfind(close_tag) + len(close_tag)
        return text[idx:].strip()
    return text


def _format_history(history: list) -> str:
    """Format conversation history for LLM context (last 3 turns max)."""
    from langchain_core.messages import HumanMessage, AIMessage

    lines = []
    # Take last 3 user-assistant exchanges
    entries = []
    for m in history:
        if isinstance(m, HumanMessage):
            entries.append(("用户", m.content or ""))
        elif isinstance(m, AIMessage):
            entries.append(("助手", m.content or ""))

    # Only include last 3 entries
    for role, content in entries[-6:]:  # up to 3 exchanges (user+assistant per turn)
        # Truncate file content to keep prompt focused
        _text = content
        if "[上传文件内容]" in _text:
            _text = _text[:200] + "…[文件内容已省略]"
        lines.append(f"{role}: {_text[:500]}")

    return "\n".join(lines)


def rewrite(user_input: str, history: list | None = None, llm_func=None) -> list[dict]:
    if not user_input or not user_input.strip():
        return []

    text = user_input.strip()

    # Tier 0: File marker — [文件: xxx.ext], pure syntax, no LLM
    _filenames = _extract_filenames(text)
    if _filenames:
        return [{"tool": "parse_file_tool", "params": {"filename": _filenames[0]}}]

    # Tier 1: LLM with full conversation context
    if llm_func:
        result = llm_func(text, history)
        if result:
            return result

    # Tier 2: Keyword fallback (only when LLM unavailable)
    from services.task.semantic_router import _keyword_route
    _user_text = _strip_file_content(text)
    # Multi-intent splitting: "A然后B" / "A同时B" / "A再B" → 不限段数
    _segs = re.split(r'\s*(?:然后|同时|并且|再)\s*', _user_text)
    _matched = []
    _seen = set()
    for _seg in _segs:
        _seg = _seg.strip()
        if not _seg:
            continue
        _kw = _keyword_route(_seg)
        if _kw and _kw not in _seen:
            _matched.append({"tool": _kw, "params": {}})
            _seen.add(_kw)
    if len(_matched) >= 2:
        return _matched
    if _matched:
        return _matched

    return []
