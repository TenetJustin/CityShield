import asyncio

from backend.app import paradise
from backend.app.adapters.weather import NWSAdapter


def test_geography_is_paradise_and_has_source_hashes():
    package = paradise.geography()
    assert package["features"][0]["properties"]["geoid"] == "0655520"
    assert len(package["features"]) > 1000
    assert len(package["source_files"]) == 2
    assert all(len(value) == 64 for value in package["source_files"].values())
    historical = paradise.historical_final_perimeter()
    assert historical["properties"]["incident_number"] == "00016737"
    assert historical["properties"]["not_time_series"] is True
    terrain = paradise.terrain_samples()
    assert terrain["grid_size"] == 7
    assert len(terrain["samples"]) == 49
    assert all(sample["resolution_m"] == 1 for sample in terrain["samples"])
    assert "display-only" in terrain["purpose"]


def test_live_source_failure_stays_visible_and_does_not_invent_fire(monkeypatch):
    async def broken_weather(*_args, **_kwargs):
        raise RuntimeError("NWS unavailable")

    async def no_incidents(*_args, **_kwargs):
        return []

    monkeypatch.setattr(NWSAdapter, "fetch_hourly", broken_weather)
    monkeypatch.setattr(paradise.WFIGSAdapter, "fetch", no_incidents)
    monkeypatch.delenv("FIRMS_MAP_KEY", raising=False)
    monkeypatch.setattr(paradise, "_cached", None)
    monkeypatch.setattr(paradise, "_cached_until", 0)
    result = asyncio.run(paradise.live_snapshot())
    assert result["sources"]["noaa-nws"]["status"] == "unavailable"
    assert result["sources"]["nifc-wfigs"]["status"] == "ok"
    assert result["sources"]["nasa-firms"]["status"] == "not_configured"
    assert result["hourly_forecast"] == []
    assert result["incidents"] == []
    assert result["operational_prediction_ready"] is False


def test_nws_uses_source_update_time_not_current_clock():
    payload = {"properties": {"updateTime": "2026-10-17T06:31:24+00:00", "periods": [{
        "number": 1, "startTime": "2026-10-17T02:00:00-07:00", "temperature": 67,
        "temperatureUnit": "F", "windSpeed": "7 mph", "windDirection": "ENE",
        "relativeHumidity": {"value": 26},
    }]}}
    assert NWSAdapter.parse_hourly(payload)[0]["forecast_issued_at"] == "2026-10-17T06:31:24+00:00"
