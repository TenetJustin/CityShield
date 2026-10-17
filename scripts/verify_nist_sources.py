"""Verify the four NIST Camp Fire map PDFs against the timeline manifest.

This downloads ~105 MB from nist.gov. It is a local audit step, not part of the
runtime image. The PDFs are not committed; only hashes, byte sizes and page
counts are written to data/paradise/nist_source_verification.json.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[1]
TIMELINE = ROOT / "data" / "paradise" / "camp_fire_nist_timeline.json"
DEST = ROOT / "data" / "paradise" / "nist_source_verification.json"


def main() -> None:
    timeline = json.loads(TIMELINE.read_text(encoding="utf-8"))
    checks = []
    with tempfile.TemporaryDirectory() as directory:
        with httpx.Client(timeout=120, follow_redirects=True) as client:
            for window in timeline["windows"]:
                response = client.get(window["source_url"])
                response.raise_for_status()
                content = response.content
                path = Path(directory) / f"{window['id']}.pdf"
                path.write_bytes(content)
                digest = hashlib.sha256(content).hexdigest()
                pages = None
                try:
                    import pymupdf

                    document = pymupdf.open(path)
                    pages = len(document)
                    page = document[0]
                    page_size = [round(page.rect.width, 2), round(page.rect.height, 2)]
                except ImportError:
                    page_size = None
                checks.append({
                    "window_id": window["id"],
                    "source_url": window["source_url"],
                    "sha256": digest,
                    "expected_sha256": window["sha256"],
                    "sha256_matches": digest == window["sha256"],
                    "bytes": len(content),
                    "pages": pages,
                    "page_size_pt": page_size,
                    "projection": "NAD83 California State Plane Zone 2 / Lambert Conformal Conic (per map legend)",
                    "status": "verified" if digest == window["sha256"] else "mismatch",
                    "digitized": False,
                    "notes": "Map symbols and annotations are embedded in a raster image; no machine-readable spatial layer was extracted.",
                })
    result = {
        "schema_version": "1.0",
        "source": "nist.gov document endpoints",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "all_verified": all(item["sha256_matches"] for item in checks),
    }
    DEST.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {DEST}: all_verified={result['all_verified']}")


if __name__ == "__main__":
    main()
