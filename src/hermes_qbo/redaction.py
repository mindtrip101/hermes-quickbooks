from __future__ import annotations

import re
from typing import Any

SECRET_KEY_RE = re.compile(
    r"(password|secret|token|refresh|access_token|client_secret|authorization|bearer|apikey|api_key|credential)",
    re.I,
)
SECRET_VALUE_RE = re.compile(
    r"(Bearer\s+)[A-Za-z0-9._~+/=-]+|"
    r"(eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)",
    re.I,
)


def redact_text(value: str) -> str:
    return SECRET_VALUE_RE.sub(lambda m: (m.group(1) or "") + "[redacted]", value)


def redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for key, val in obj.items():
            if SECRET_KEY_RE.search(str(key)):
                out[key] = "[redacted]"
            else:
                out[key] = redact(val)
        return out
    if isinstance(obj, list):
        return [redact(item) for item in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj


def contains_secret(obj: Any) -> bool:
    dumped = str(obj)
    if "Bearer " in dumped and len(dumped) > 20:
        if SECRET_VALUE_RE.search(dumped):
            return True
    return False
