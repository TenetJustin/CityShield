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

City-specific adapters must additionally record source CRS, native resolution, units, license, refresh interval and any transformation into the 500 m decision grid. Missing values remain missing and must not be silently replaced with zero.

