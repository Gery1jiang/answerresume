"""Output audit / PII detection for LLM-generated content.

Scans agent output for sensitive data leakage (phone, email, ID numbers)
and system prompt leakage attempts before delivering to the frontend.
"""

import re
from dataclasses import dataclass

# ── PII patterns ─────────────────────────────────────

PHONE_PATTERN = re.compile(
    r'(?<!\d)(?:\+?86[-.\s]?)?1[3-9]\d{9}(?!\d)'
)

EMAIL_PATTERN = re.compile(
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
)

ID_CARD_PATTERN = re.compile(
    r'[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]'
)

# ── System prompt leakage patterns ────────────────────

LEAKAGE_PATTERNS = [
    re.compile(r'忽略.*(?:指令|规则|设定|system prompt|系统提示)', re.IGNORECASE),
    re.compile(r'(?:告诉我|说出).*(?:system prompt|系统提示词|你的提示词)', re.IGNORECASE),
    re.compile(r'重置.*(?:身份|设定|角色)', re.IGNORECASE),
    re.compile(r'ignore.*(?:above|previous|all).*instructions', re.IGNORECASE),
]


@dataclass
class AuditResult:
    has_pii: bool = False
    has_leakage: bool = False
    phone_count: int = 0
    email_count: int = 0
    id_count: int = 0
    masked_text: str = ""


def scan(text: str) -> AuditResult:
    """Scan text for PII and system prompt leakage.

    Returns an AuditResult with detection counts and masked text.
    """
    result = AuditResult()
    if not text:
        return result

    # PII detection
    phones = PHONE_PATTERN.findall(text)
    emails = EMAIL_PATTERN.findall(text)
    ids = ID_CARD_PATTERN.findall(text)

    result.phone_count = len(phones)
    result.email_count = len(emails)
    result.id_count = len(ids)
    result.has_pii = bool(phones or emails or ids)

    # Build masked text
    masked = text
    for p in phones:
        masked = masked.replace(p, p[:3] + "****" + p[-4:])
    for e in emails:
        at = e.find("@")
        masked = masked.replace(e, e[:3] + "***" + e[at:])
    for i in ids:
        masked = masked.replace(i, i[:4] + "********" + i[-4:])
    result.masked_text = masked

    # Leakage detection
    for pat in LEAKAGE_PATTERNS:
        if pat.search(text):
            result.has_leakage = True
            break

    return result


def mask_pii(text: str) -> str:
    """Convenience: scan and return masked text (original if no PII)."""
    result = scan(text)
    return result.masked_text if result.has_pii else text


def audit_tool_output(tool_name: str, text: str) -> dict:
    """Audit a tool's output text. Returns audit metadata dict."""
    result = scan(text)
    audit = {
        "tool": tool_name,
        "has_pii": result.has_pii,
        "has_leakage": result.has_leakage,
        "phone_count": result.phone_count,
        "email_count": result.email_count,
        "id_count": result.id_count,
    }
    if result.has_pii or result.has_leakage:
        print(f"[output_audit] WARNING: tool={tool_name} pii={result.has_pii} leakage={result.has_leakage}")
    return audit
