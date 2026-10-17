from backend.app.adapters.firms import FIRMSAdapter
from backend.app.adapters.base import BoundingBox
from backend.app.adapters.weather import NWSAdapter
from backend.app.adapters.wfigs import WFIGSAdapter


def test_firms_csv_parser():
    records = FIRMSAdapter.parse_csv(
        "latitude,longitude,acq_date,acq_time,confidence,frp,satellite,instrument\n"
        "34.1,-118.2,2026-01-01,1200,h,12.5,N,VIIRS\n"
    )
    assert records[0]["frp"] == 12.5
    assert records[0]["latitude"] == 34.1
    assert records[0]["acquired_at"] == "2026-01-01T12:00:00Z"


def test_firms_historical_request_includes_start_date():
    url = FIRMSAdapter("secret", "VIIRS_SNPP_SP").request_url(
        BoundingBox(-121.7, 39.68, -121.52, 39.85),
        days=2,
        start_date="2018-11-08",
    )
    assert url.endswith("/VIIRS_SNPP_SP/-121.7,39.68,-121.52,39.85/2/2018-11-08")


def test_nws_hourly_parser():
    records = NWSAdapter.parse_hourly(
        {
            "properties": {
                "updated": "2026-01-01T00:00:00Z",
                "periods": [
                    {
                        "number": 1,
                        "startTime": "2026-01-01T01:00:00+00:00",
                        "temperature": 70,
                        "temperatureUnit": "F",
                        "windSpeed": "10 to 20 mph",
                        "windDirection": "W",
                        "relativeHumidity": {"value": 18},
                        "shortForecast": "Windy",
                    }
                ],
            }
        }
    )
    assert records[0]["wind_speed_m_s"] == 6.706
    assert records[0]["humidity_pct"] == 18


def test_wfigs_geojson_parser_ignores_missing_geometry():
    records = WFIGSAdapter.parse_geojson(
        {
            "features": [
                {"properties": {"name": "A"}, "geometry": {"type": "Point", "coordinates": [0, 0]}},
                {"properties": {"name": "B"}, "geometry": None},
            ]
        }
    )
    assert [item["properties"]["name"] for item in records] == ["A"]
