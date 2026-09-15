from __future__ import annotations

import re

SECRET_PATTERNS = (
    re.compile(r"(?:gsk|sk|pk)_[A-Za-z0-9_-]{8,}"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{12,}=*", re.I),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_./+:-]{8,}"),
)


def contains_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


def redact_secrets(value: str) -> str:
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED_SECRET]", value)
    return value
