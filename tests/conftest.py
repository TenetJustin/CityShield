"""Keep test audit writes out of the developer and deployed runtime chain."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


_TEST_RUNTIME = tempfile.TemporaryDirectory(prefix="cityshield-tests-")
os.environ["CITYSHIELD_AUDIT_PATH"] = str(
    Path(_TEST_RUNTIME.name) / "audit.jsonl"
)
