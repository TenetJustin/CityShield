from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .schemas import Observation


def demo_observations() -> list[Observation]:
    base = datetime(2025, 8, 14, 20, 0, tzinfo=timezone.utc)
    raw = [
        ("wind_speed", None, 9.0, 0),
        ("wind_direction", None, 75.0, 0),
        ("humidity", None, 16.0, 0),
        ("hotspot", "B1", 0.91, 2),
        ("hotspot", "B2", 0.78, 7),
        ("perimeter", "A1", 0.62, 12),
    ]
    return [
        Observation(
            event_id="synthetic-demo-001",
            kind=kind,
            cell_id=cell_id,
            value=value,
            unit={
                "wind_speed": "m/s",
                "wind_direction": "degree",
                "humidity": "percent",
                "hotspot": "confidence_0_1",
                "perimeter": "confidence_0_1",
            }[kind],
            valid_at=base + timedelta(minutes=offset),
            available_at=base + timedelta(minutes=offset + 2),
            source="CityShield synthetic replay",
            quality_flag="synthetic-demo",
        )
        for kind, cell_id, value, offset in raw
    ]


def demo_incident() -> dict:
    """Small, deterministic incident bundle used for offline-safe judging.

    It is intentionally labelled synthetic and exercises the same timeline,
    layer and comparison contracts that a city-specific historical package
    will implement later.
    """

    base = datetime(2025, 8, 14, 20, 0, tzinfo=timezone.utc)
    frames = [
        {
            "minute": 0,
            "timestamp": base.isoformat(),
            "observed_cells": ["B1"],
            "hotspot_cells": ["B1"],
            "note": "First high-confidence thermal detection",
            "weather": {"wind_speed": 9.0, "wind_direction": 75.0, "humidity": 16.0},
        },
        {
            "minute": 30,
            "timestamp": (base + timedelta(minutes=30)).isoformat(),
            "observed_cells": ["B1", "B2"],
            "hotspot_cells": ["B1", "B2"],
            "note": "Heat signature expands into the adjacent fuel cell",
            "weather": {"wind_speed": 9.8, "wind_direction": 78.0, "humidity": 15.0},
        },
        {
            "minute": 60,
            "timestamp": (base + timedelta(minutes=60)).isoformat(),
            "observed_cells": ["A1", "B1", "B2"],
            "hotspot_cells": ["A1", "B2"],
            "note": "Observed edge reaches the upslope cell",
            "weather": {"wind_speed": 10.6, "wind_direction": 82.0, "humidity": 14.0},
        },
        {
            "minute": 120,
            "timestamp": (base + timedelta(minutes=120)).isoformat(),
            "observed_cells": ["A1", "A2", "B1", "B2"],
            "hotspot_cells": ["A2", "B2"],
            "note": "Final exercise perimeter used for model scoring",
            "weather": {"wind_speed": 8.7, "wind_direction": 91.0, "humidity": 18.0},
        },
    ]
    return {
        "incident_id": "synthetic-demo-001",
        "name": "Ridgeline validation exercise",
        "data_mode": "synthetic-demo",
        "offline_ready": True,
        "duration_minutes": 120,
        "frames": frames,
        "resources": [
            {
                "resource_id": "ENGINE-12",
                "label": "Engine 12",
                "kind": "engine",
                "cell_id": "C2",
                "available_from_minute": 30,
                "status": "staged",
            },
            {
                "resource_id": "UAS-04",
                "label": "UAS 04",
                "kind": "drone",
                "cell_id": "A3",
                "available_from_minute": 60,
                "status": "monitoring",
            },
        ],
        "events": [
            {"minute": 0, "type": "detection", "label": "First hotspot"},
            {"minute": 30, "type": "resource", "label": "Engine staged"},
            {"minute": 60, "type": "observation", "label": "Perimeter update"},
            {"minute": 120, "type": "review", "label": "Outcome available"},
        ],
        "quality": {
            "label": "Synthetic exercise — not an observed incident",
            "complete": True,
            "time_aligned": True,
            "limitations": [
                "No operational accuracy claim",
                "Resource positions are illustrative",
                "Replace with one independently sourced historical event before final judging",
            ],
        },
    }

