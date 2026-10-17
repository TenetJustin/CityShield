# Data and delivery gates

CityShield separates a reliable competition demonstration from claims that require city-specific evidence. A missing live feed must never prevent judging, and cached or synthetic records must never be presented as live.

## Three release levels

| Level | Required evidence | Current state | Allowed claim |
| --- | --- | --- | --- |
| Competition demo | Deterministic offline replay, forecast, decision, audit and UI | Ready | Working research prototype |
| Historical validation | A separately held-out incident with time-aligned hotspot, progression, weather and outcome data | Paradise FIRMS replay and within-incident scoring complete; progression, historical weather, outcomes and independent incident still missing | Historical replay; no generalization claim yet |
| Live city pilot | Monitored feeds, spatial mapper, freshness alarms and rehearsed fallback | Paradise public map, weather and incident queries integrated; prediction and response gates pending | Live advisory feed, never an official warning |

The `GET /api/v1/delivery/readiness` endpoint exposes these gates to the console. The bundled `GET /api/v1/demo/incident` package is deliberately synthetic, versionable and offline-safe.

The Paradise replay is documented in [its source manifest](../data/paradise/SOURCES.md) and is now the default judging view. The legacy synthetic exercise remains collapsed. The public-data panel and current NOAA/NIFC queries do not imply that the live-city gate has passed.

## Dataset acceptance checklist

Accept a source only when the team can record:

1. owner, license and retrieval URL;
2. native spatial resolution, CRS and coverage;
3. observation time, provider publication time and ingestion time;
4. missingness, duplicates, outliers and expected update interval;
5. point, raster or polygon mapping into the CityShield grid;
6. a cached raw snapshot that can reproduce the demonstration;
7. a visible failure state when the source is stale or unavailable.

Do not interpolate missing timestamps silently. Do not treat satellite detection time as publication time. Do not mix forecast weather with observations without retaining the forecast issue time.

## Minimum viable city package

Before replacing the synthetic label, the selected city must have:

- one fire with at least four perimeter or comparable progression snapshots;
- FIRMS detections or another independently sourced hotspot record;
- hourly wind, humidity and temperature with issue/valid times;
- terrain and fuel layers with documented vintage and resolution;
- population and critical facilities suitable for area-level exposure;
- a written data-quality report and a frozen replay bundle.

Road closures, evacuation zones and response-resource telemetry improve the decision story but are not permitted to block the core forecast demonstration. If unavailable, CityShield must label those layers illustrative and exclude them from accuracy claims.

## Competition fallback policy

The judging path runs entirely from a versioned local replay package. Live adapters run as an enhancement. If an external request is unavailable, slow or stale, the interface must:

1. stop calling the data live;
2. show the source and last successful timestamp;
3. switch to the labelled cached replay;
4. preserve the evidence snapshot ID and audit record;
5. continue the full Detect → Predict → Decide → Review demonstration.

## Freeze milestones

- **City freeze:** no city change after its historical incident passes the acceptance checklist.
- **Data freeze:** produce a versioned offline bundle and checksum before final integration.
- **Feature freeze:** after the replay, prediction, approval and LinuxONE smoke tests pass, accept only defect fixes.
- **Demo freeze:** rehearse the same offline path used by judges and retain screenshots/logs proving LinuxONE execution.

