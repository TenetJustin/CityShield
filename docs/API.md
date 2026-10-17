# API and state transitions

Interactive OpenAPI documentation is available at `/docs` while the backend is running.

| Method and path | Purpose |
|---|---|
| `GET /health` | Process health and deployed model version |
| `GET /api/v1/readiness` | Platform readiness and remaining city-specific blockers |
| `GET /api/v1/paradise/history/firms` | Frozen 2018 FIRMS package and its data-quality gate |
| `GET /api/v1/paradise/exposure/population` | Pre-fire ACS area-level exposure package and quality gate |
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

## Error semantics

- `404`: requested decision or RSI candidate does not exist.
- `409`: stale run identity, invalid lifecycle transition, or missing baseline forecast.
- `422`: schema, time, range, cell or scenario validation failure.
- Upstream source failures are reported by adapters and must not silently fall back to data labeled live.

