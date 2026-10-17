"""Rebuild the display-only 2018 Camp Fire final-boundary overlay."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
from shapely.geometry import mapping, shape


ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = (
    "https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/"
    "California_Historic_Fire_Perimeters/FeatureServer/0"
)
GLOBAL_ID = "e1118f7f-b1a8-43b6-b6d0-d03fe3b1136e"


def main() -> None:
    response = httpx.get(
        SOURCE_URL + "/query",
        params={
            "where": f"GlobalID='{GLOBAL_ID}'",
            "outFields": "FIRE_NAME,YEAR_,GIS_ACRES,INC_NUM,GlobalID",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        },
        timeout=40,
    )
    response.raise_for_status()
    features = response.json().get("features", [])
    if len(features) != 1 or features[0]["properties"]["INC_NUM"] != "00016737":
        raise ValueError("CAL FIRE Camp Fire feature identity could not be verified")
    feature = features[0]
    geography = json.loads((ROOT / "data/paradise/geography_2025.geojson").read_text())
    town = shape(geography["features"][0]["geometry"])
    clipped = shape(feature["geometry"]).intersection(town).simplify(
        0.00005, preserve_topology=True
    )
    result = {
        "type": "Feature",
        "geometry": mapping(clipped),
        "properties": {
            "name": "2018 Camp Fire",
            "kind": "historical_final_perimeter_town_clip",
            "incident_number": "00016737",
            "global_id": GLOBAL_ID,
            "official_final_acres": feature["properties"]["GIS_ACRES"],
            "display_only": True,
            "source_url": SOURCE_URL,
            "source_owner": "CAL FIRE FRAP",
            "processing": "intersected with Census 2025 Paradise boundary and simplified to 0.00005 degree for display",
            "not_time_series": True,
        },
    }
    target = ROOT / "data/paradise/camp_fire_final_2018_town_clip.geojson"
    target.write_text(json.dumps(result, separators=(",", ":")))
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()
