# CityShield

The console shows a separate Paradise public-data panel with 2D Census geography, a 3D view of sampled USGS terrain, NOAA hourly weather forecast, NIFC incident query and optional NASA FIRMS detections. A new frozen-data status panel reads the machine-readable quality report, and the real-data chain now uses one shared **500 m Paradise grid (841 cells)** with stable `P-row-col` IDs. The legacy 3×3 synthetic exercise remains below and is always labelled synthetic.

CityShield is a single-city wildfire world-model prototype for the IBM Z Datathon 2026 track **Real-Time AI for Critical Decisions**.

It implements a transparent **Detect → Decide → Respond** loop:

1. ingest time-stamped hotspot and weather observations;
2. update a grid-based city belief state;
3. forecast wildfire risk at 30, 60 and 120 minutes;
4. rank evacuation and resource-staging recommendations;
5. require human approval and retain a hash-chained audit trail;
6. evaluate completed incidents through a controlled RSI shadow loop.

> Research prototype only. It is not an official warning, evacuation, dispatch or fire-spread system.

## Current status

- A frozen **Paradise 500 m grid** (841 cells, 3 km town buffer) is the single spatial contract for FIRMS hotspots, ACS population exposure, Census roads, terrain and the backend model. See [Paradise replay data](docs/PARADISE_REPLAY.md).
- The **NASA FIRMS Camp Fire package** contains 2,017 VIIRS detections in 9 snapshots from 2018-11-08 11:50 PT to 2018-11-09 14:01 PT. It is an observation-point layer, not a perimeter.
- The **NIST Camp Fire timeline** has 4 continuous windows with re-verified source hashes. The map symbols are raster-embedded and remain **undigitized**, so NIST is a temporal constraint only and cannot be used for spatial scoring.
- The **data quality report** (`data/paradise/data_quality_report.json`) declares 11 pass, 8 warn, 4 blocked and 3 context checks. Blocked layers are NIST spatial extraction, fuel, water and critical facilities. The website shows the same machine-readable report.
- The **ACS 2013–2017 population** layer allocates 21,785 people to the town clip, 17.6% below the ACS place estimate; it contains no resident locations.
- The **real replay** has 14 frames (9 FIRMS observations, 5 NIST boundaries), 591 observed cells and no inserted fake frames. The 688-minute overnight gap is preserved.
- The **strict time-forward evaluation** scores 6 short-lead windows: precision 0.254, recall 0.709, IoU 0.230, arrival median error 21 min. The long-lead bucket has only 2 windows and is marked **evidence insufficient**. NIST is not scored spatially.
- The legacy 3×3 synthetic exercise remains available for offline judging and is labelled synthetic everywhere; it is not a historical result.
- The backend and demo run on IBM LinuxONE with the included UBI container definition.
- Controlled RSI can score an incident and create a shadow candidate, but cannot silently change the active model.
- What-if runs share the frozen baseline evidence snapshot and return a paired simulation ID.
- The judging path is offline-safe: a labelled cached exercise, delivery gates and source fallbacks keep the full demo runnable without external APIs.
- Remaining blockers are NIST spatial digitization, observed fuel, water and facility layers, a calibrated spread model, official shelters/resources and an authorized operating agreement.

## Run locally

```bash
python -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/uvicorn backend.app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for the API. To run the web console:

```bash
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite, normally **http://localhost:5173/**. Do not open `frontend/index.html` as a `file://` URL: Vite must serve the React modules, and the API must be running.

If ports 8000 or 5173 are already used by another checkout, start the services on separate ports and keep the API URL and CORS origin matched:

```bash
CITYSHIELD_CORS_ORIGINS=http://127.0.0.1:5174 .venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8001
# In a second terminal:
cd frontend
VITE_API_URL=http://127.0.0.1:8001 npm run dev -- --host 127.0.0.1 --port 5174
```

Then open **http://127.0.0.1:5174/**.

The Paradise public-data panel is available without a NASA key. The API paths
`/api/v1/paradise/geography` and `/api/v1/paradise/live` expose source details.
See [Paradise sources and acceptance gaps](data/paradise/SOURCES.md). The live
panel is not a validated fire prediction or official emergency service.

To build the two frozen historical inputs without storing credentials in the
repository, export the free provider keys in your shell and run:

```bash
export FIRMS_MAP_KEY="..."
python scripts/build_paradise_firms_history.py
export CENSUS_API_KEY="..."
python scripts/build_paradise_population.py
```

The builders write source metadata and explicit quality gates. FIRMS points are
not treated as perimeters, and ACS area estimates are not treated as resident
locations.

## Run the demo

```bash
curl -X POST http://localhost:8000/api/v1/demo/reset
curl -X POST http://localhost:8000/api/v1/demo/replay
curl http://localhost:8000/api/v1/demo/incident
curl http://localhost:8000/api/v1/delivery/readiness
curl http://localhost:8000/api/v1/predict
curl -X POST http://localhost:8000/api/v1/decisions/recommend
```

## LinuxONE

```bash
podman build -f Containerfile.linuxone -t cityshield:latest .
podman run --rm -p 8000:8000 cityshield:latest
```

See [Architecture](docs/ARCHITECTURE.md), [data contract](docs/DATA_CONTRACT.md), and [city-selection checklist](docs/CITY_SELECTION.md).

## Verification

```bash
make verify
# With the API running:
python scripts/smoke_test.py
```

The automated suite covers temporal visibility, ingestion idempotency, deterministic forecasts, paired scenarios, decision review/outcome separation, audit-chain integrity, external adapter parsing, and RSI promotion gates.

## Documentation

- [Paradise replay data, grid and quality gates](docs/PARADISE_REPLAY.md)
- [API and state transitions](docs/API.md)
- [Model card and limitations](docs/MODEL_CARD.md)
- [LinuxONE deployment](docs/DEPLOY_LINUXONE.md)
- [Real-data integration runbook](docs/REAL_DATA_INTEGRATION.md)
- [Data and delivery gates](docs/DELIVERY_GATES.md)
- [Datathon demo script](docs/DEMO_SCRIPT.md)
- [Submission checklist](docs/SUBMISSION.md)
- [Front-end functions and layout](docs/FRONTEND_EXPERIENCE.md)
- [Security notes](docs/SECURITY.md)

## Acknowledgement

The workflow design is inspired by the public `cityos-flood` research prototype—especially its snapshot identity, ensemble forecasting, paired counterfactuals, advisory decision loop and controlled improvement boundary. CityShield's wildfire implementation is newly written and does not reuse Shenzhen parameters or claim that flood dynamics transfer to fire behavior.

