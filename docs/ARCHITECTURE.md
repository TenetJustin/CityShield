# CityShield architecture

CityShield preserves the reusable flow of `cityos-flood` while replacing flood-specific dynamics and actions with wildfire state, spread, exposure, evacuation and resource decisions.

```mermaid
flowchart TB
  S[External streams: FIRMS, weather, perimeters, roads] --> I

  subgraph L[IBM LinuxONE]
    subgraph RT[Real-time critical-decision loop]
      I[Ingest + validate + align] --> O[Evidence snapshot]
      O --> D[DETECT: assimilate and identify change]
      D --> W[Wildfire world state]
      W --> P[PREDICT: 30/60/120 min ensemble]
      P --> X[SIMULATE: wind/resource/road scenarios]
      X --> C[DECIDE: exposure and constrained recommendations]
      C --> H[RESPOND: human approval]
      H --> A[Hash-chained audit and outcome]
      A -. feedback .-> O
    end

    subgraph RSI[Controlled RSI — asynchronous, never silent]
      E[Post-event scoring] --> G[Error diagnosis]
      G --> K[Shadow candidate]
      K --> B[Held-out replay + safety gate]
      B --> V[Human approval + version registry + rollback]
    end

    A --> E
    V -. approved next version only .-> W
  end

  H --> UI[React decision console]
  UI --> H
```

## World-model contract

- **World:** city cells, adjacency, fuel, terrain, weather, roads, population and facilities.
- **State:** burning probability, intensity, remaining fuel and uncertainty by cell.
- **Action:** advisory evacuation preparation, route review and resource staging.
- **Cost:** exposed population/facilities, route loss, uncertainty and resource constraints.
- **Safety:** no automatic public warning, evacuation order or dispatch; human review is mandatory.

## LinuxONE boundary

The API, stream/replay processor, state estimator, ensemble forecast, decision engine, controlled RSI and audit log run inside the LinuxONE deployment boundary. External public data providers remain outside it. The web console can be served separately or from the same platform.

