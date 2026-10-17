from backend.app import history
from backend.app.history import build_firms_history_package, profile_firms_detections


def detection(minute: str, latitude: float = 39.75, satellite: str = "N") -> dict:
    return {
        "latitude": latitude,
        "longitude": -121.60,
        "acq_date": "2018-11-08",
        "acq_time": minute,
        "acquired_at": f"2018-11-08T{minute[:2]}:{minute[2:]}:00Z",
        "confidence": "nominal",
        "frp": 10.0,
        "satellite": satellite,
        "instrument": "VIIRS",
        "product": "VIIRS_SNPP_SP",
        "raw": {},
    }


def test_firms_history_requires_four_unique_times_and_deduplicates():
    rows = [detection(value) for value in ("0800", "0900", "1000", "1100")]
    rows.append(dict(rows[0]))
    profile = profile_firms_detections(rows)
    assert profile["quality"]["raw_record_count"] == 5
    assert profile["quality"]["record_count"] == 4
    assert profile["quality"]["duplicate_count"] == 1
    assert profile["quality"]["accepted_for_replay"] is True


def test_firms_history_rejects_incomplete_temporal_coverage():
    profile = profile_firms_detections([detection("0800"), detection("0900")])
    assert profile["quality"]["unique_acquisition_times"] == 2
    assert profile["quality"]["accepted_for_replay"] is False


def test_package_never_contains_a_map_key():
    package = build_firms_history_package(
        [detection(value) for value in ("0800", "0900", "1000", "1100")],
        source_requests=[{"product": "VIIRS_SNPP_SP", "start_date": "2018-11-08"}],
        bounds={"west": -121.7, "south": 39.68, "east": -121.52, "north": 39.85},
    )
    assert package["source_owner"] == "NASA LANCE FIRMS"
    assert "map_key" not in str(package).lower()
    assert package["quality"]["accepted_for_replay"] is True


def test_missing_population_package_is_reported_without_inventing_data(monkeypatch, tmp_path):
    monkeypatch.setattr(history, "ROOT", tmp_path)
    monkeypatch.setattr(history, "PARADISE_POPULATION", tmp_path / "missing.geojson")
    result = history.load_population_exposure()
    assert result["status"] == "not_built"
    assert result["accepted_for_area_exposure"] is False
    assert "package" not in result
