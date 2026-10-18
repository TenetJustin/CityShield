import asyncio

from backend.app import paradise_nowcast


def snapshot(detections):
    return {
        "area": "Paradise, California",
        "fetched_at": "2026-10-18T08:00:00+00:00",
        "sources": {
            "nasa-firms": {"status": "ok", "fetched_at": "2026-10-18T08:00:00+00:00", "count": len(detections)},
            "noaa-nws": {"status": "ok", "fetched_at": "2026-10-18T08:00:00+00:00", "count": 1},
            "nifc-wfigs": {"status": "ok", "fetched_at": "2026-10-18T08:00:00+00:00", "count": 0},
        },
        "hourly_forecast": [{
            "valid_at": "2026-10-18T01:00:00-07:00",
            "forecast_issued_at": "2026-10-18T07:30:00+00:00",
            "temperature": 68,
            "temperature_unit": "F",
            "wind_speed_m_s": 6.0,
            "wind_direction": "NE",
            "humidity_pct": 25,
        }],
        "incidents": [],
        "satellite_detections": detections,
    }


def test_live_nowcast_abstains_without_mapped_detections(monkeypatch):
    async def fake_live(force=False):
        return snapshot([])

    monkeypatch.setattr(paradise_nowcast.paradise, "live_snapshot", fake_live)
    result = asyncio.run(paradise_nowcast.build_nowcast())
    assert result["status"] == "abstained_no_observations"
    assert result["forecasts"] == {}
    assert result["actions"][0]["action"] == "Continue source monitoring"
    assert "not a perimeter" in result["observation"]["interpretation"]


def test_live_nowcast_maps_inputs_predicts_and_queues_human_actions(monkeypatch):
    detections = [{
        "longitude": -121.62114,
        "latitude": 39.772698,
        "acquired_at": "2026-10-18T07:55:00Z",
        "frp": 12.5,
    }]

    async def fake_live(force=False):
        return snapshot(detections)

    monkeypatch.setattr(paradise_nowcast.paradise, "live_snapshot", fake_live)
    result = asyncio.run(paradise_nowcast.build_nowcast())
    assert result["status"] == "advisory_ready"
    assert result["observation"]["mapped_seed_cells"] == ["P-16-12"]
    assert set(result["forecasts"]) == {"30", "60", "120"}
    assert all(item["source_mode"] == "live_firms_nws" for item in result["forecasts"].values())
    assert result["weather"]["wind_from_deg"] == 45
    assert result["weather"]["temperature_c"] == 20
    assert result["decision_status"] == "pending_human_review"
    assert all(action["requires_human_review"] for action in result["actions"])


def test_live_nowcast_pauses_when_weather_is_incomplete(monkeypatch):
    payload = snapshot([{"longitude": -121.62114, "latitude": 39.772698}])
    payload["hourly_forecast"] = []

    async def fake_live(force=False):
        return payload

    monkeypatch.setattr(paradise_nowcast.paradise, "live_snapshot", fake_live)
    result = asyncio.run(paradise_nowcast.build_nowcast())
    assert result["status"] == "input_incomplete"
    assert result["forecasts"] == {}
    assert result["actions"][0]["action"] == "Restore required live inputs"
