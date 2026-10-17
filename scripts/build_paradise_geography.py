"""Extract a small, reproducible Paradise map from official Census TIGER files.

Run after downloading the two 2025 ZIPs listed in data/paradise/SOURCES.md.
Requires pyshp and shapely only for this build step; the app reads plain JSON.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import shapefile
from shapely.geometry import shape, mapping


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "sources"
DEST = ROOT / "data" / "paradise" / "geography_2025.geojson"
PLACE_ZIP = SOURCES / "tl_2025_06_place.zip"
ROADS_ZIP = SOURCES / "tl_2025_06007_roads.zip"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    with shapefile.Reader(str(PLACE_ZIP)) as reader:
        found = next(
            record for record in reader.iterShapeRecords()
            if record.record.as_dict().get("GEOID") == "0655520"
        )
        town = shape(found.shape.__geo_interface__)
    road_features = []
    with shapefile.Reader(str(ROADS_ZIP)) as reader:
        for record in reader.iterShapeRecords():
            road = shape(record.shape.__geo_interface__)
            if not road.intersects(town):
                continue
            clipped = road.intersection(town)
            if clipped.is_empty:
                continue
            simplified = clipped.simplify(0.000035, preserve_topology=True)
            if simplified.is_empty:
                continue
            props = record.record.as_dict()
            road_features.append({
                "type": "Feature",
                "geometry": mapping(simplified),
                "properties": {
                    "name": props.get("FULLNAME") or "Unnamed road",
                    "mtfcc": props.get("MTFCC"),
                },
            })
    output = {
        "type": "FeatureCollection",
        "name": "Paradise, California: 2025 Census town boundary and clipped roads",
        "crs": "EPSG:4326",
        "bbox": [round(value, 6) for value in town.bounds],
        "source_vintage": "2025 TIGER/Line",
        "source_files": {
            PLACE_ZIP.name: digest(PLACE_ZIP),
            ROADS_ZIP.name: digest(ROADS_ZIP),
        },
        "features": [
            {"type": "Feature", "geometry": mapping(town), "properties": {"kind": "town_boundary", "geoid": "0655520"}},
            *road_features,
        ],
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(output, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {DEST}: {len(road_features)} road features")


if __name__ == "__main__":
    main()
