# Paradise pre-fire vegetation clip

This package clips LANDFIRE 2016 Remap Existing Vegetation Type (EVT) to the rectangular bounds of the 841 cells in CityShield's Paradise 500 m grid. It is a circa-2016 vegetation proxy for the 2018 Camp Fire, not a 2018 observation or a current vegetation map.

## Files

- `paradise_lf2016_evt.tif`: native 30 m categorical raster, EPSG:5070, 593 columns by 601 rows, losslessly compressed.
- `paradise_lf2016_evt_legend.csv`: source legend restricted to codes present in the clip; `pixel_count` counts pixels in the entire rectangular clip, not only grid interiors.
- `clip_report.json`: input identity, requested extent, processing and quality checks.
- `LF2016_EVT_CONUS.xml`: original provider metadata.

## Source and use

Provider: LANDFIRE, USGS and USDA Forest Service. Product: LF 2016 Remap EVT, CONUS.

- Data access: https://www.landfire.gov/data
- Product/version: https://landfire.gov/data/lf2016
- Use and scale guidance: https://www.landfire.gov/faqs
- USGS copyright guidance: https://www.usgs.gov/faqs/are-usgs-reportspublications-copyrighted

USGS-produced data are in the U.S. public domain unless otherwise noted. Preserve the bundled product metadata and acknowledge LANDFIRE/USGS when reusing this derived clip. The repository code license does not replace source-data terms.

## Reproduce

Download and extract the official LF2016 EVT CONUS package, retaining its `Tif` and `CSV_Data` subdirectories. From the repository root:

```sh
python -m pip install -r scripts/requirements-vegetation.txt
python scripts/clip_evt.py --source-dir /path/to/LF2016_EVT_CONUS
```

The script transforms WGS84 cell bounds into the source CRS, rounds outward to whole pixels and reads only the corresponding raster window. It preserves native pixel values, resolution and CRS and verifies the saved raster matches the source window. It does not load the full national raster into memory.

## Limitations

- The rectangle includes extra pixels outside the project grid, especially at projected edges. It is not a precise town-boundary mask.
- The 30 m output resolution does not imply parcel-level accuracy.
- EVT codes are categories, not continuous fuel intensity. Do not average their numeric IDs or substitute them directly for the model's fuel parameter.
- No 500 m cell aggregation, model change, API or frontend integration is included.
- This historical layer must not be presented as current vegetation for live monitoring.
