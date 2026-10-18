# CityShield architecture

CityShield preserves the reusable flow of `cityos-flood` while replacing flood-specific dynamics and actions with wildfire state, spread, exposure, evacuation and resource decisions.

```mermaid
flowchart TB
  S[Near-real-time streams: FIRMS + NOAA] --> I

  subgraph L[IBM LinuxONE]
    subgraph RT[Real-time critical-decision loop]
      I[Ingest + validate + map to Paradise grid] --> O[Evidence snapshot]
      O --> D[DETECT: assimilate and identify change]
      D --> W[Wildfire world state]
      W --> P[PREDICT: 30/60/120 min ensemble]
      P --> X[SIMULATE: wind/resource/road scenarios]
      P --> Q[RESPONSE SCENARIO: aggregate evacuation queues and simulated resource allocation]
      X --> C[DECIDE: exposure and constrained recommendations]
      Q --> UI
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
  A --> R[Incident replay: observed vs predicted]
  R --> UI
```

The real-time and RSI paths are deliberately separated. Detect/Decide/Respond stays deterministic for a frozen evidence snapshot; RSI only consumes completed-event outcomes and may propose a versioned shadow candidate.

The implemented minimum live path is `FIRMS + NOAA → Paradise 500 m grid →
24-member 30/60/120-minute ensemble → population exposure → ranked advisory
actions → human review → audit hash`. A missing required feed returns
`input_incomplete`; zero mapped detections returns `abstained_no_observations`.
The system never fills either state with the 2018 replay.

## World-model contract

- **World:** city cells, adjacency, fuel, terrain, weather, roads, population and facilities.
- **State:** burning probability, intensity, remaining fuel and uncertainty by cell.
- **Action:** advisory evacuation preparation, route review and resource staging.
- **Cost:** exposed population/facilities, route loss, uncertainty and resource constraints.
- **Safety:** no automatic public warning, evacuation order or dispatch; human review is mandatory.

## LinuxONE boundary

The API, stream/replay processor, state estimator, ensemble forecast, decision engine, controlled RSI and audit log run inside the LinuxONE deployment boundary. External public data providers remain outside it. The web console can be served separately or from the same platform.

## Identity chain

`evidence_snapshot_id → forecast_run_id → simulation_run_id → decision_run_id → audit hash`

Every recommendation can therefore be traced to a frozen set of observations, model/config version, scenario and human review. A duplicate observation is ignored by its provider identity rather than silently changing the state twice.

The JSONL audit writer takes an operating-system file lock, refreshes the chain
head from disk and fsyncs each append. This prevents separate application or test
processes from assigning the same sequence. Tests use an isolated audit path and
never append to the developer or deployed runtime chain.

Paradise response scenarios use a parallel identity chain:

`grid/data version + order or issue time + seed/strategy + hazard setting → simulation_id`

They do not enter the operational decision chain and do not create dispatches.

## Delivery boundary

The live-data path is the primary competition flow. The historical Camp Fire
package provides a reproducible demonstration and time-forward evaluation when
external feeds are unavailable. The interface labels live, cached, historical
and synthetic modes explicitly; source failure may lead the presenter to the
separate replay, but the live endpoint itself abstains and never silently
changes provenance.

## Remaining city-specific boundary

The platform is complete up to the spatial adapter. Selecting a city must provide its boundary, cell geometry, local projection, authoritative road/evacuation layers, critical facilities and at least one historical incident. Those inputs may change the calibrated model and decisions, but not the contracts above.

