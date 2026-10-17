"""Clip LF2016 EVT to the union bounds of CityShield's 841 grid cells."""
from pathlib import Path
import csv
import json
import math
import argparse
import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-dir', type=Path, required=True, help='Extracted LF2016_EVT_CONUS directory')
parser.add_argument('--grid', type=Path, default=ROOT / 'data/paradise/paradise_grid_500m.json')
args = parser.parse_args()
SOURCE = args.source_dir
GRID = args.grid
OUT = ROOT / 'data/vegetation'
OUT.mkdir(parents=True, exist_ok=True)
grid = json.loads(GRID.read_text())
# Use actual cell bounds rather than slightly different rounded extent metadata.
b = [c['bounds_wgs84'] for c in grid['cells']]
bounds = [min(x['west'] for x in b), min(x['south'] for x in b),
          max(x['east'] for x in b), max(x['north'] for x in b)]
target = OUT / 'paradise_lf2016_evt.tif'
with rasterio.open(SOURCE / 'Tif/LF2016_EVT_CONUS.tif') as src:
    projected = transform_bounds('EPSG:4326', src.crs, *bounds, densify_pts=21)
    raw = from_bounds(*projected, transform=src.transform)
    left, top = math.floor(raw.col_off), math.floor(raw.row_off)
    right, bottom = math.ceil(raw.col_off + raw.width), math.ceil(raw.row_off + raw.height)
    win = Window(left, top, right-left, bottom-top).intersection(Window(0, 0, src.width, src.height))
    arr = src.read(1, window=win)
    profile = src.profile.copy()
    profile.update(width=arr.shape[1], height=arr.shape[0],
                   transform=src.window_transform(win), compress='deflate', count=1)
    with rasterio.open(target, 'w', **profile) as dst:
        dst.write(arr, 1)
        dst.update_tags(source='LANDFIRE 2016 Remap EVT',
                        purpose='Pre-fire vegetation proxy, not observed 2018 vegetation',
                        grid_version=grid['grid_version'])
    nodata = src.nodata
    vals, counts = np.unique(arr, return_counts=True)
    frequency = {int(v):int(n) for v,n in zip(vals, counts)}
    report = {'source':'LANDFIRE LF2016_EVT_CONUS/Tif/LF2016_EVT_CONUS.tif',
              'grid_version':grid['grid_version'], 'grid_file':GRID.name,
              'aoi_bounds_wgs84':bounds, 'output_crs':str(src.crs),
              'resolution_native_units':list(src.res), 'shape':list(arr.shape),
              'nodata':nodata, 'nodata_pixels':frequency.get(int(nodata),0) if nodata is not None else None,
              'method':'Native-resolution rectangular window covering all grid cells; no resampling. Includes pixels outside grid at rectangle edges.',
              'limitations':['Circa-2016 vegetation proxy for 2018; not a fuel model.',
                             'Category codes are labels, not numeric fuel intensity.']}
with (SOURCE / 'CSV_Data/LF2016_EVT.csv').open(encoding='utf-8-sig', newline='') as f:
    reader=csv.DictReader(f); columns=reader.fieldnames
    legend=[r for r in reader if int(r['VALUE']) in frequency]
with (OUT/'paradise_lf2016_evt_legend.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=columns+['pixel_count']);writer.writeheader()
    for r in legend:writer.writerow({**r,'pixel_count':frequency[int(r['VALUE'])]})
report['unmatched_category_codes']=sorted(set(frequency)-{int(r['VALUE']) for r in legend})
with rasterio.open(target) as check:
    assert np.array_equal(check.read(1), arr), 'Output differs from source window'
report['output_bytes']=target.stat().st_size
(OUT/'clip_report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
print('Saved:',target)
