from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from threading import RLock
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - LinuxONE and macOS both provide fcntl.
    fcntl = None

from .schemas import utc_now


class AuditLog:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._records: list[dict[str, Any]] = []
        self._lock = RLock()
        if self.path and self.path.is_file():
            with self.path.open(encoding="utf-8") as handle:
                if fcntl:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
                try:
                    self._records = self._read(handle)
                finally:
                    if fcntl:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            verification = self.verify()
            if not verification["valid"]:
                raise ValueError(f"invalid audit chain on disk: {verification}")

    @staticmethod
    def _read(handle) -> list[dict[str, Any]]:
        handle.seek(0)
        return [json.loads(line) for line in handle if line.strip()]

    @staticmethod
    def _verify_records(records: list[dict[str, Any]]) -> dict[str, Any]:
        previous_hash = "GENESIS"
        for expected_sequence, record in enumerate(records, start=1):
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
        return {"valid": True, "records": len(records), "head_hash": previous_hash}

    def append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            handle = None
            try:
                if self.path:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    handle = self.path.open("a+", encoding="utf-8")
                    if fcntl:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                    disk_records = self._read(handle)
                    verification = self._verify_records(disk_records)
                    if not verification["valid"]:
                        raise ValueError(f"invalid audit chain on disk: {verification}")
                    self._records = disk_records
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
                if handle:
                    handle.seek(0, os.SEEK_END)
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                return record
            finally:
                if handle:
                    if fcntl:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                    handle.close()

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._records)

    def verify(self) -> dict[str, Any]:
        return self._verify_records(self._records)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a+", encoding="utf-8") as handle:
                    if fcntl:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                    try:
                        handle.seek(0)
                        handle.truncate()
                        handle.flush()
                        os.fsync(handle.fileno())
                    finally:
                        if fcntl:
                            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

