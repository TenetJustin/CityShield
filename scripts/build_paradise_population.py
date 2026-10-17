"""Build a pre-Camp-Fire Paradise population exposure layer.

Sources:
- 2017 TIGER/Line California block groups and 2018 place boundary
- 2013-2017 ACS 5-year total population estimates and margins of error

Population is allocated into the Paradise boundary by block-group area. It is
an area-level exposure estimate, never a resident location dataset.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import sys
import zipfile
from pathlib import Path
from typing import Any

import httpx
import shapefile
from shapely.geometry import mapping, shape
from shapely.ops import transform, unary_union


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BLOCK_GROUP_URL = "https://www2.census.gov/geo/tiger/TIGER2017/BG/tl_2017_06_bg.zip"
PLACE_URL = "https://www2.census.gov/geo/tiger/TIGER2018/PLACE/tl_2018_06_place.zip"
ACS_URL = "https://api.census.gov/data/2017/acs/acs5"
BUTTE_COUNTY = "007"
PARADISE_PLACE = "55520"
TARGET = ROOT / "data" / "paradise" / "population_acs_2017_block_groups.geojson"


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def read_shapefile_zip(content: bytes, stem: str) -> shapefile.Reader:
    archive = zipfile.ZipFile(io.BytesIO(content))
    return shapefile.Reader(
        shp=io.BytesIO(archive.read(f"{stem}.shp")),
        shx=io.BytesIO(archive.read(f"{stem}.shx")),
        dbf=io.BytesIO(archive.read(f"{stem}.dbf")),
    )


def local_area(geometry, latitude: float = 39.75) -> float:
    radius = 6_371_008.8
    longitude_scale = math.cos(math.radians(latitude))
    return transform(
        lambda x, y, z=None: (
            math.radians(x) * radius * longitude_scale,
            math.radians(y) * radius,
        ),
        geometry,
    ).area


def build_exposure(
    town,
    block_groups: list[dict[str, Any]],
    place_population: int,
) -> dict[str, Any]:
    features = []
    clipped_geometries = []
    missing_population = []
    for item in block_groups:
        geometry = item["geometry"]
        if not geometry.intersects(town):
            continue
        clipped = geometry.intersection(town)
        if clipped.is_empty:
            continue
        population = item.get("population")
        margin = item.get("margin_of_error")
        if population is None or population < 0:
            missing_population.append(item["geoid"])
            continue
        source_area = local_area(geometry)
        fraction = local_area(clipped) / source_area if source_area else 0
        allocated = population * fraction
        allocated_margin = margin * fraction if margin is not None and margin >= 0 else None
        clipped_geometries.append(clipped)
        features.append(
            {
                "type": "Feature",
                "geometry": mapping(clipped),
                "properties": {
                    "geoid": item["geoid"],
                    "source_population": population,
                    "source_population_moe": margin,
                    "area_fraction_in_paradise": round(fraction, 6),
                    "allocated_population": round(allocated, 2),
                    "allocated_population_moe": (
                        round(allocated_margin, 2) if allocated_margin is not None else None
                    ),
                    "allocation_method": "block-group population multiplied by area overlap",
                    "vintage": "2013-2017 ACS 5-year",
                },
            }
        )

    town_area = local_area(town)
    covered_area = local_area(unary_union(clipped_geometries)) if clipped_geometries else 0
    allocated_total = sum(feature["properties"]["allocated_population"] for feature in features)
    margin_values = [
        feature["properties"]["allocated_population_moe"]
        for feature in features
        if feature["properties"]["allocated_population_moe"] is not None
    ]
    aggregate_margin = math.sqrt(sum(value * value for value in margin_values))
    difference_pct = (
        abs(allocated_total - place_population) / place_population * 100 if place_population else None
    )
    coverage = covered_area / town_area if town_area else 0
    accepted = coverage >= 0.99 and not missing_population and bool(features)
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "area": "Paradise town, California",
            "intended_use": "historical area-level population exposure for the 2018 Camp Fire replay",
            "not_resident_locations": True,
            "source_population_vintage": "2013-2017 ACS 5-year",
            "place_population_estimate": place_population,
            "allocated_population_estimate": round(allocated_total, 2),
            "allocated_population_moe": round(aggregate_margin, 2),
            "difference_from_place_estimate_pct": (
                round(difference_pct, 2) if difference_pct is not None else None
            ),
            "quality": {
                "intersecting_block_groups": len(features),
                "missing_population_geoids": missing_population,
                "town_area_coverage_pct": round(coverage * 100, 4),
                "accepted_for_area_exposure": accepted,
            },
            "limitations": [
                "Area-weighting assumes population is uniformly distributed inside each block group.",
                "ACS estimates include sampling error; they are not exact resident counts.",
                "The layer contains no household addresses, live occupancy or individual locations.",
            ],
        },
    }


def main() -> None:
    api_key = os.getenv("CENSUS_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("CENSUS_API_KEY is required; do not paste it into source code")
    with httpx.Client(timeout=90, follow_redirects=True) as client:
        block_group_response = client.get(BLOCK_GROUP_URL)
        block_group_response.raise_for_status()
        place_response = client.get(PLACE_URL)
        place_response.raise_for_status()
        block_group_rows = client.get(
            ACS_URL,
            params={
                "get": "NAME,B01003_001E,B01003_001M",
                "for": "block group:*",
                "in": "state:06 county:007 tract:*",
                "key": api_key,
            },
        )
        block_group_rows.raise_for_status()
        place_rows = client.get(
            ACS_URL,
            params={
                "get": "NAME,B01003_001E,B01003_001M",
                "for": f"place:{PARADISE_PLACE}",
                "in": "state:06",
                "key": api_key,
            },
        )
        place_rows.raise_for_status()

    bg_reader = read_shapefile_zip(block_group_response.content, "tl_2017_06_bg")
    place_reader = read_shapefile_zip(place_response.content, "tl_2018_06_place")
    town_records = [
        record
        for record in place_reader.shapeRecords()
        if record.record.as_dict().get("PLACEFP") == PARADISE_PLACE
    ]
    if len(town_records) != 1:
        raise SystemExit("Paradise 2018 place boundary was not uniquely identified")
    town = shape(town_records[0].shape.__geo_interface__)

    population_payload = block_group_rows.json()
    columns = population_payload[0]
    population_by_geoid = {}
    for values in population_payload[1:]:
        row = dict(zip(columns, values))
        geoid = f"{row['state']}{row['county']}{row['tract']}{row['block group']}"
        population_by_geoid[geoid] = {
            "population": int(row["B01003_001E"]),
            "margin_of_error": int(row["B01003_001M"]),
        }

    block_groups = []
    for record in bg_reader.shapeRecords():
        properties = record.record.as_dict()
        if properties.get("COUNTYFP") != BUTTE_COUNTY:
            continue
        geoid = properties["GEOID"]
        population = population_by_geoid.get(geoid, {})
        block_groups.append(
            {
                "geoid": geoid,
                "geometry": shape(record.shape.__geo_interface__),
                **population,
            }
        )
    place_payload = place_rows.json()
    place_population = int(dict(zip(place_payload[0], place_payload[1]))["B01003_001E"])
    result = build_exposure(town, block_groups, place_population)
    result["metadata"]["sources"] = {
        "block_groups": BLOCK_GROUP_URL,
        "block_groups_sha256": sha256(block_group_response.content),
        "place_boundary": PLACE_URL,
        "place_boundary_sha256": sha256(place_response.content),
        "population_api": ACS_URL,
    }
    TARGET.write_text(json.dumps(result, indent=2), encoding="utf-8")
    quality = result["metadata"]["quality"]
    print(
        f"Wrote {TARGET} with {quality['intersecting_block_groups']} block groups; "
        f"coverage={quality['town_area_coverage_pct']}%; "
        f"accepted_for_area_exposure={quality['accepted_for_area_exposure']}"
    )


if __name__ == "__main__":
    main()
