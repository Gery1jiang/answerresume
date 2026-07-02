"""Admin Agent 意图分类器 — 前置意图检测，分类结果仅为 Prompt 组装参考，不做强路由。"""

import re

# Intent keys matching agent_prompt_builder module keys
INTENT_PARSE = "agent_intent_parse_file"
INTENT_RESUME = "agent_intent_generate_resume"
INTENT_INTERVIEW = "agent_intent_create_interview"
INTENT_KNOWLEDGE = "agent_intent_knowledge_edit"

# Fast keyword patterns (used as primary path — sufficient for most cases)
_KEYWORD_PATTERNS: dict[str, list[str]] = {
    INTENT_PARSE: [
        r"解析图片", r"看看这张图", r"图片里是什么", r"OCR",
        r"识别这张图", r"提取图片文字", r"翻译图片",
    ],
    INTENT_RESUME: [
        r"生成.*简历", r"做.*简历", r"制作.*简历", r"帮我写.*简历",
        r"根据.*生成.*简历", r"给我.*简历", r"简历.*生成",
    ],
    INTENT_INTERVIEW: [
        r"创建.*面试", r"新增.*面试", r"录入.*面试.*记录", r"面试记录",
    ],
    INTENT_KNOWLEDGE: [
        r"修改.*知识库", r"改名", r"换.*经历", r"换人", r"知识库.*修改",
    ],
}


def classify(user_input: str) -> list[str]:
    """Classify admin user intent intent_keys.

    Uses keyword matching for speed and determinism.
    Returns a list of matched intent keys (may be empty).
    The caller should always include common sections (role, tools, rules)
    regardless of classification result — this is advisory only.
    """
    if not user_input:
        return []

    matched: list[str] = []
    for intent_key, patterns in _KEYWORD_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, user_input):
                matched.append(intent_key)
                break

    return matched


def has_file_upload(user_input: str) -> bool:
    """Check if user_input contains a file upload marker."""
    return bool(re.search(r'\[文件:\s*\S+\.\w+\]', user_input))
