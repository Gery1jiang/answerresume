import re

_MAX_MESSAGE_LENGTH = 50000

_INJECTION_PATTERNS = [
    (re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|directives|commands)", re.I), "指令忽略攻击"),
    (re.compile(r"(forget|discard|disregard|override)\s+(all\s+)?(your\s+)?(instructions|rules|prompt|guidelines)", re.I), "指令忽略攻击"),
    (re.compile(r"you\s+(are\s+)?(now|must|will)\s+(act\s+(as|like)|behave\s+(as|like)|become|pretend|play\s+(the\s+)?role\s+of)", re.I), "角色劫持攻击"),
    (re.compile(r"(your\s+)?system\s+(prompt|message|instruction)", re.I), "系统提示泄露"),
    (re.compile(r"(do\s+|just\s+)?(whatever|anything|anyway)\s+(you\s+)?want", re.I), "约束解除攻击"),
    (re.compile(r"new\s+(prompt|instruction|rule|command)", re.I), "新指令注入"),
    (re.compile(r"output\s+(your\s+)?(system|initial|first|original)\s+(prompt|instructions|message)", re.I), "提示词泄露"),
    (re.compile(r" DAN |do\s+anything\s+now", re.I), "越狱攻击"),
    (re.compile(r"\[system\]|\[end\s+of\s+system\]|\[user\]|\[assistant\]|\[\/system\]", re.I), "角色边界混淆攻击"),
    (re.compile(r"(reveal|print|display|show|leak|dump)\s+(your\s+)?(system|instructions|prompt)", re.I), "提示词泄露"),
    (re.compile(r"(忽略|忘记|无视).{0,10}(以上|之前|前面|所有|全部).{0,10}(指令|规则|提示|设定|要求)", re.I), "中文指令忽略攻击"),
    (re.compile(r"(输出|显示|泄露|告诉我).{0,10}(系统提示|prompt|系统指令|初始设定)", re.I), "中文提示泄露"),
]


def check_message(text: str) -> tuple[bool, str]:
    if not text or not text.strip():
        return True, ""
    if len(text) > _MAX_MESSAGE_LENGTH:
        return False, f"消息长度超过限制（{len(text)} > {_MAX_MESSAGE_LENGTH}）"

    for pattern, label in _INJECTION_PATTERNS:
        if pattern.search(text):
            return False, f"检测到疑似prompt injection：{label}"

    return True, ""
