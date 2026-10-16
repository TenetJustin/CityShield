# Data contract

Every dynamic record must retain both event time and system availability time.

| Field | Meaning |
|---|---|
| `event_id` | Incident/replay identifier |
| `kind` | Hotspot, perimeter, wind, humidity or another registered observation type |
| `cell_id` | City grid cell when spatially applicable |
| `valid_at` | Physical observation or forecast-valid time, including timezone |
| `available_at` | Time the record could actually be used by CityShield |
| `source` | Provider and product identity |
| `quality_flag` | Observed, derived, forecast or synthetic demo |
| `value` | Value in the unit fixed by the registered observation type |
| `unit` | Explicit unit; never inferred from a column name |
| `provider_record_id` | Stable upstream ID used for idempotency when available |
| `forecast_issued_at` | Provider issue time required for forecast records |
| `source_crs` | Native coordinate reference system when spatial |
| `native_resolution_m` | Approximate native spatial resolution when known |

City-specific adapters must additionally record source CRS, native resolution, units, license, refresh interval and any transformation into the 500 m decision grid. Missing values remain missing and must not be silently replaced with zero.

For observations, `available_at >= valid_at`. Forecast values are the exception: they may be available before their future valid time, but must include `forecast_issued_at <= available_at`. Historical validation must filter on `available_at <= replay_time` to avoid hindsight leakage.

## Canonical spatial layers

| Layer | Required fields after city selection |
|---|---|
| Grid cells | `cell_id`, geometry, centroid, area, CRS, resolution |
| Fuel/terrain | fuel class/load, elevation, slope, aspect, source version |
| Exposure | population estimate, buildings, critical facilities, timestamp |
| Roads | edge/node IDs, direction, capacity proxy, closure state, valid/available time |
| Response resources | resource ID/type, status, location, capacity, valid/available time |

Raw files remain immutable. Transformations produce a manifest containing input hashes, processing version, CRS transformation and aggregation rule.

