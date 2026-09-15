"""Small dependency-free JSONL logger used by translation jobs."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UTC = timezone.utc


class StructuredLogger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def emit(self, event: str, message: str = "", level: str = "INFO", **fields: Any) -> dict[str, Any]:
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level.upper(),
            "event": event,
            "message": message,
            **fields,
        }
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
        return record


def get_job_logger(paths: dict) -> StructuredLogger:
    return StructuredLogger(paths.get("events_log") or Path(paths["job_dir"]) / "events.jsonl")
