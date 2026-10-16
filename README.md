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
- Real data adapters are placeholders for NASA FIRMS, NOAA/NWS/RAWS/HRRR, WFIGS, LANDFIRE, USGS 3DEP, roads and Census/CRE.
- The backend and demo can run on IBM LinuxONE with the included UBI container definition.
- Controlled RSI can create shadow candidates but cannot silently change the active model.

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
curl http://localhost:8000/api/v1/predict
curl -X POST http://localhost:8000/api/v1/decisions/recommend
```

## LinuxONE

```bash
podman build -f Containerfile.linuxone -t cityshield:latest .
podman run --rm -p 8000:8000 cityshield:latest
```

See [Architecture](docs/ARCHITECTURE.md), [data contract](docs/DATA_CONTRACT.md), and [city-selection checklist](docs/CITY_SELECTION.md).

