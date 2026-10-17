# CityShield

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

- The city is intentionally configurable and currently uses a synthetic 3×3 demonstration grid.
- Generic NASA FIRMS, NOAA/NWS and WFIGS clients are implemented. They remain disabled until a city boundary and spatial mapper are configured. LANDFIRE, USGS 3DEP and local response data have explicit file contracts.
- The backend and demo can run on IBM LinuxONE with the included UBI container definition.
- Controlled RSI can score an incident and create a shadow candidate, but cannot silently change the active model.
- What-if runs share the frozen baseline evidence snapshot and return a paired simulation ID.
- The console has an interactive 3D synthetic terrain, animated forecast timeline, four risk bands and a guided Understand → Test → Review workflow.
- A FireTrace-inspired incident-replay mode separates observed edge, hotspot, resources and forecast layers, with actual-versus-predicted comparison.
- The judging path is offline-safe: a labelled cached exercise, delivery gates and source fallbacks keep the full demo runnable without external APIs.
- The remaining blockers are deliberately city-specific: selecting the city, replacing the synthetic grid, and mapping authoritative local data.

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

