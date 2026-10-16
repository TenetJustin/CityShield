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
            valid_at=base + timedelta(minutes=offset),
            available_at=base + timedelta(minutes=offset + 2),
            source="CityShield synthetic replay",
            quality_flag="synthetic-demo",
        )
        for kind, cell_id, value, offset in raw
    ]

