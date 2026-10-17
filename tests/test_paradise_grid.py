from fastapi.testclient import TestClient

from backend.app import paradise_grid
from backend.app.main import app


client = TestClient(app)


def test_shared_grid_is_one_resolution_and_stable_ids():
    artifact = paradise_grid.grid()
    assert artifact["grid_version"] == "paradise-500m-v1"
    assert artifact["resolution_m"] == 500
    assert artifact["cell_count"] == len(artifact["cells"])
    assert artifact["cell_count"] == artifact["extent"]["cols"] * artifact["extent"]["rows"]
    ids = [cell["id"] for cell in artifact["cells"]]
    assert len(ids) == len(set(ids))
    for cell in artifact["cells"]:
        assert cell["id"] == f"P-{cell['row']:02d}-{cell['col']:02d}"
        assert cell["size_m"] == 500
        assert "population" in cell["sources"]
        assert "population" in cell["status"]


def test_point_lookup_round_trips_cell_centroids():
    artifact = paradise_grid.grid()
    for cell in artifact["cells"][::97]:
        centroid = cell["centroid"]
        found = paradise_grid.cell_for_lonlat(centroid["longitude"], centroid["latitude"])
        assert found is not None
        assert found["id"] == cell["id"]
    assert paradise_grid.cell_for_lonlat(-120.0, 35.0) is None


def test_grid_population_reconciles_with_acs_clip():
    artifact = paradise_grid.grid()
    total = sum(cell["population"] for cell in artifact["cells"])
    assert abs(total - artifact["town"]["population_allocated"]) < 0.5
    town_cells = [cell for cell in artifact["cells"] if cell["in_town"]]
    assert town_cells
    assert all(cell["population"] >= 0 for cell in artifact["cells"])
    assert sum(cell["population"] for cell in town_cells) > 20_000


def test_missing_layers_are_declared_not_invented():
    artifact = paradise_grid.grid()
    assert artifact["layers"]["water"]["status"] == "missing"
    assert artifact["layers"]["critical_facilities"]["status"] == "missing"
    assert artifact["layers"]["fuel"]["status"] == "assumed"
    assert artifact["layers"]["shelters"]["status"] == "scenario"
    assert all(cell["status"]["water"] == "missing" for cell in artifact["cells"])


def test_data_quality_report_exposes_gaps_and_matches_grid_version():
    report = paradise_grid.data_quality()
    artifact = paradise_grid.grid()
    assert report["overall"]["status"] == "usable_with_declared_gaps"
    assert report["overall"]["accepted_for_historical_replay"] is True
    assert report["overall"]["accepted_for_nist_spatial_scoring"] is False
    assert report["overall"]["operational_ready"] is False
    assert report["data_version"] == artifact["data_version"]
    ids = {check["id"] for check in report["checks"]}
    assert {"firms-gap", "nist-spatial-digitization", "population-vintage"} <= ids
    nist_check = next(check for check in report["checks"] if check["id"] == "nist-spatial-digitization")
    assert nist_check["status"] == "blocked"
    assert report["coverage"]["firms"]["record_count"] == 2017
    assert report["coverage"]["firms"]["unique_acquisition_times"] == 9
    assert len(report["inputs"]) == 6


def test_data_quality_report_contains_no_credentials():
    text = str(paradise_grid.data_quality()).lower()
    for forbidden in ("map_key", "api_key", "census_api_key", "firms_map_key"):
        assert forbidden not in text


def test_exposure_summary_is_explicitly_area_level():
    summary = paradise_grid.exposure_summary()
    assert summary["status"] == "derived"
    assert summary["total_population"] > 20_000
    assert summary["population_vintage"] == "2013-2017 ACS 5-year"
    assert any("no addresses" in item.lower() for item in summary["limitations"])


def test_paradise_grid_api_endpoints():
    grid_response = client.get("/api/v1/paradise/grid")
    assert grid_response.status_code == 200
    payload = grid_response.json()
    assert payload["cell_count"] == 841
    assert len(payload["cells"]) == 841

    summary = client.get("/api/v1/paradise/grid/summary").json()
    assert summary["cell_count"] == 841
    assert summary["quality"]["status"] == "usable_with_declared_gaps"

    quality = client.get("/api/v1/paradise/data-quality")
    assert quality.status_code == 200
    assert quality.json()["overall"]["status_label"] == "Usable with declared gaps"

    config = client.get("/api/v1/paradise/replay/config").json()
    assert config["config"]["forecast"]["members"] == 24
    assert config["config"]["grid"]["resolution_m"] == 500
    assert config["status_policy"]["predicted"].startswith("model output")


def test_paradise_exposure_api_endpoint():
    response = client.get("/api/v1/paradise/exposure/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "derived"
    assert payload["cells_with_population"] > 0
