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
            frozen_payload = json.loads(json.dumps(payload, default=str))
            record = {
                "sequence": len(self._records) + 1,
                "recorded_at": utc_now().isoformat(),
                "event_type": event_type,
                "payload": frozen_payload,
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

    def verify(self) -> dict[str, Any]:
        previous_hash = "GENESIS"
        for expected_sequence, record in enumerate(self._records, start=1):
            if record.get("sequence") != expected_sequence:
                return {"valid": False, "failed_sequence": expected_sequence, "reason": "sequence"}
            if record.get("previous_hash") != previous_hash:
                return {"valid": False, "failed_sequence": expected_sequence, "reason": "chain"}
            body = {key: value for key, value in record.items() if key != "hash"}
            canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
            digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if digest != record.get("hash"):
                return {"valid": False, "failed_sequence": expected_sequence, "reason": "hash"}
            previous_hash = digest
        return {"valid": True, "records": len(self._records), "head_hash": previous_hash}

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            if self.path and self.path.exists():
                self.path.unlink()

