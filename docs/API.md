# API and state transitions

Interactive OpenAPI documentation is available at `/docs` while the backend is running.

| Method and path | Purpose |
|---|---|
| `GET /health` | Process health and deployed model version |
| `GET /api/v1/readiness` | Platform readiness and remaining city-specific blockers |
| `GET /api/v1/paradise/history/firms` | Frozen 2018 FIRMS package and its data-quality gate |
| `GET /api/v1/paradise/history/nist-timeline` | Verified NIST Camp Fire observation windows and scoring gate |
| `GET /api/v1/paradise/exposure/population` | Pre-fire ACS area-level exposure package and quality gate |
| `GET /api/v1/paradise/grid` | Shared 500 m grid with per-cell provenance |
| `GET /api/v1/paradise/grid/summary` | Grid, exposure and quality summary |
| `GET /api/v1/paradise/data-quality` | Machine-readable data-quality report |
| `GET /api/v1/paradise/replay` | Real FIRMS/NIST replay frames and source status |
| `GET /api/v1/paradise/replay/frame?at=...` | Latest real frame at or before a timestamp |
| `GET /api/v1/paradise/forecast?at=...&lead_minutes=...` | Deterministic time-forward grid forecast |
| `GET /api/v1/paradise/evaluation` | Strict time-forward evaluation package and evidence status |
| `GET /api/v1/paradise/evaluation/summary` | Compact evaluation summary |
| `GET /api/v1/paradise/response/config` | Declared evacuation/resource assumptions and status policy |
| `POST /api/v1/paradise/evacuation/simulate` | Run one aggregate synthetic-resident evacuation scenario |
| `POST /api/v1/paradise/evacuation/compare` | Compare assumed evacuation-order times with one fixed seed |
| `POST /api/v1/paradise/resources/simulate` | Allocate simulated resources by exposure, travel time or no-action baseline |
| `GET /api/v1/sources` | Adapter, credential and city-dependency status |
| `GET /api/v1/state` | Current belief state and recent observations |
| `POST /api/v1/observations` | Validate, deduplicate and assimilate one observation |
| `GET /api/v1/predict` | Create a frozen 30/60/120-minute baseline forecast |
| `POST /api/v1/scenarios/simulate` | Run a paired What-if against the frozen baseline |
| `POST /api/v1/decisions/recommend` | Produce an advisory recommendation |
| `POST /api/v1/decisions/{id}/review` | Human approve/reject step |
| `POST /api/v1/decisions/{id}/outcome` | Record what actually happened |
| `POST /api/v1/rsi/evaluate` | Score a completed event and create a shadow candidate |
| `POST /api/v1/rsi/candidates/{id}/gate` | Record held-out, safety and human gates |
| `GET /api/v1/audits` | Read and verify the hash-chained audit trail |
| `GET /api/v1/demo/stream` | Server-Sent Events replay for the real-time demo |

## Decision lifecycle

```text
pending_human_review
  ├─ approved_for_coordination ─┐
  └─ rejected ─────────────────┼─ closed (outcome recorded)
```

Approval does not execute a public warning or operational command. It records that a human accepted the recommendation for coordination.

## Paradise response scenarios

The response endpoints are deterministic scenario tools. Each response includes a
`simulation_id`, `model_version`, grid/data versions, assumptions and limitations.
Residents are cell-level synthetic agents generated from aggregate ACS exposure.
Road capacity, departure behaviour, reception areas, resource home cells and
effectiveness are assumptions. Resource routes are model paths rather than GPS
tracks, and the protected-population value is an illustrative expected-exposure
calculation without suppression feedback.

Population accounting follows:

```text
total = pre-evacuated + evacuated + trapped + unaccommodated + not-cleared
```

`clearance_minutes` is populated only when the simulated population is fully cleared. In an incomplete scenario it is `null`; `last_successful_arrival_minutes` remains available and must not be described as clearance time.

An early scenario with no FIRMS-seeded forecast reports `no_forecast`; a zero
trapped count in that state is not evidence of safety.

## Error semantics

- `404`: requested decision or RSI candidate does not exist.
- `409`: stale run identity, invalid lifecycle transition, or missing baseline forecast.
- `422`: schema, time, range, cell or scenario validation failure.
- Upstream source failures are reported by adapters and must not silently fall back to data labeled live.

