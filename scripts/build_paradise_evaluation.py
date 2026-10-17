"""Precompute the strict time-forward Camp Fire evaluation package.

Run after the grid and data-quality artifacts are current. The API serves the
frozen JSON and refuses it when the data/model version no longer matches.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app import paradise_eval


def main() -> None:
    package = paradise_eval.build_evaluation()
    paradise_eval.EVALUATION_PATH.write_text(
        json.dumps(package, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"Wrote {paradise_eval.EVALUATION_PATH}")
    print(f"data_version={package['data_version']} model={package['model_version']} replay={package['replay_id']}")
    for bucket_id, bucket in package["by_lead"].items():
        current = bucket["current"]
        print(
            f"  {bucket_id}: windows={bucket['window_count']} "
            f"evidence={bucket['evidence']['status']} "
            f"precision={current['precision']} recall={current['recall']} iou={current['iou']}"
        )


if __name__ == "__main__":
    main()
