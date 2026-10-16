from __future__ import annotations

import hashlib
import json
from pathlib import Path
from threading import RLock
from typing import Any

from .schemas import utc_now


class AuditLog:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._records: list[dict[str, Any]] = []
        self._lock = RLock()

    def append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            previous_hash = self._records[-1]["hash"] if self._records else "GENESIS"
            record = {
                "sequence": len(self._records) + 1,
                "recorded_at": utc_now().isoformat(),
                "event_type": event_type,
                "payload": payload,
                "previous_hash": previous_hash,
            }
            canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), default=str)
            record["hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            self._records.append(record)
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            return record

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._records)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

