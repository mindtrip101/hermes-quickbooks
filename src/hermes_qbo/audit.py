from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .redaction import redact


class AuditLog:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.last_success: str | None = None

    def write(self, record: dict[str, Any]) -> None:
        record = dict(record)
        record.setdefault("ts", datetime.now(timezone.utc).isoformat())
        line = json.dumps(redact(record), separators=(",", ":"), default=str)
        lowered = line.lower()
        for needle in ("access_token", "refresh_token", "client_secret"):
            if needle in lowered and "[redacted]" not in lowered:
                line = json.dumps({"ts": record["ts"], "error": "audit_redaction_failed", "tool": record.get("tool")})
                break
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            if record.get("success"):
                self.last_success = record["ts"]
