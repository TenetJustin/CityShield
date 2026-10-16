# Real-data integration runbook

Everything in this runbook is implemented or specified except the target city's values and files.

## 1. Freeze the city package

Create a new config from `config/city.example.json` and validate it against `config/city.schema.json`. Record city boundary version, timezone, local CRS, grid resolution and area of interest. Replace `TBD_US_CITY` only after the data package is reviewable.

## 2. Build the spatial mapper

Aggregate LANDFIRE fuel/vegetation and USGS 3DEP elevation/slope/aspect into the decision grid. Intersect population, buildings and facilities without treating coarse population estimates as exact addresses. Build a point/polygon-to-cell lookup for FIRMS and WFIGS observations.

## 3. Register dynamic sources

- Set `FIRMS_MAP_KEY` and use `FIRMSAdapter` for native detections.
- Use `NWSAdapter` at documented sampling points; preserve provider issue and valid times.
- Use `WFIGSAdapter` for incident metadata/perimeters where available.
- Map local closures, zones and resources into the canonical observation and layer contracts.

## 4. Prepare one independent event

Store raw snapshots append-only. Each replay record must have `valid_at`, `available_at`, source version and quality. Select a baseline start time, then reveal data only when `available_at` reaches the replay clock.

## 5. Validate before changing claims

Run the historical event end-to-end and report both forecast skill and system latency. Replace `synthetic-demo` with `historical-replay` only when every dynamic input is sourced. Change `data_mode` to `real` only for a monitored live feed. Keep `advisory_only=true`.

