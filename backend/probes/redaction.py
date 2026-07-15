from __future__ import annotations

import re


_PATTERNS = (
    re.compile(r"(?im)^(\s*(?:password|secret|community|pre-shared-key|private-key)\s+)(\S+).*$"),
    re.compile(r"(?i)\b((?:password|secret|community|pre-shared-key|private-key)\s*[=:]?\s*)(?!<redacted>)\S+"),
    re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)\b(snmp-server\s+community\s+)(?!<redacted>)\S+"),
)


def redact_output(value: str, *, max_bytes: int) -> tuple[str, int, bool]:
    text = value
    redactions = 0
    for pattern in _PATTERNS:
        text, count = pattern.subn(lambda match: f"{match.group(1)}<redacted>", text)
        redactions += count
    raw = text.encode("utf-8", errors="replace")
    truncated = len(raw) > max_bytes
    if truncated:
        text = raw[:max_bytes].decode("utf-8", errors="ignore") + "\n<truncated>"
    return text, redactions, truncated
