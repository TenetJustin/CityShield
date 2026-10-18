import { useEffect, useMemo, useState } from "react";

const API = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");
const CELL_ID = /^P-(\d{2})-(\d{2})$/;

async function post(path, body) {
  const response = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
  return payload;
}

async function get(path) {
  const response = await fetch(`${API}${path}`);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
  return payload;
}

function formatLocal(value) {
  return new Date(value).toLocaleString("en-US", {
    timeZone: "America/Los_Angeles",
    dateStyle: "medium",
    timeStyle: "short",
  }) + " PT";
}

function number(value) {
  return value == null ? "—" : Math.round(value).toLocaleString();
}

function hazardLabel(hazard) {
  if (!hazard) return "unknown";
  if (hazard.status === "predicted") return "predicted hazard";
  if (hazard.status === "no_forecast") return "no mapped forecast";
  if (hazard.status === "disabled_for_comparison") return "hazard disabled";
  return hazard.status;
}

function EvacuationChart({ timeline }) {
  if (!timeline?.length) return null;
  const width = 620;
  const height = 150;
  const padding = 20;
  const maxMinutes = Math.max(1, timeline[timeline.length - 1].minute);
  const maxValue = Math.max(1, ...timeline.map((point) => Math.max(point.evacuated_people, point.trapped_people, point.unaccommodated_people)));
  const point = (x, y) => `${padding + (x / maxMinutes) * (width - padding * 2)},${height - padding - (y / maxValue) * (height - padding * 2)}`;
  const line = (key) => timeline.map((item) => point(item.minute, item[key])).join(" ");
  return <svg className="evacChart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Simulated evacuation over time: evacuated, trapped and unaccommodated people">
    <rect width={width} height={height} fill="rgba(5,20,14,.45)" rx="6" />
    <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="rgba(228,238,230,.18)" />
    <line x1={padding} y1={padding} x2={padding} y2={height - padding} stroke="rgba(228,238,230,.18)" />
    <polyline points={line("evacuated_people")} fill="none" stroke="#7fc79a" strokeWidth="3" />
    <polyline points={line("trapped_people")} fill="none" stroke="#d7a84b" strokeWidth="3" />
    <polyline points={line("unaccommodated_people")} fill="none" stroke="#b05a24" strokeWidth="2" strokeDasharray="6 4" />
    <text x={padding} y={padding - 6} fill="#8fa99a" fontSize="8">people</text>
    <text x={width - padding} y={height - 5} fill="#8fa99a" fontSize="8" textAnchor="end">{maxMinutes} min</text>
    <text x={padding + 4} y={padding + 12} fill="#7fc79a" fontSize="8">evacuated</text>
    <text x={padding + 4} y={padding + 24} fill="#d7a84b" fontSize="8">trapped</text>
    <text x={padding + 4} y={padding + 36} fill="#c7885c" fontSize="8">unaccommodated</text>
  </svg>;
}

function cellPoint(cellId) {
  const match = CELL_ID.exec(cellId || "");
  if (!match) return null;
  const row = Number(match[1]);
  const col = Number(match[2]);
  return { x: col * 10 + 5, y: (28 - row) * 10 + 5 };
}

function ResponseFlowMap({ detail, resources }) {
  if (!detail) return null;
  const flows = [...(detail.cell_flows || [])]
    .filter((item) => item.path_cell_ids?.length > 1 && item.assigned_people > 0)
    .sort((left, right) => right.assigned_people - left.assigned_people)
    .slice(0, 40);
  const unassigned = (detail.cell_flows || []).filter((item) => item.unassigned_people >= 0.5);
  const assignments = (resources?.assignments || []).filter((item) => item.status === "assigned");
  return <div className="responseMapWrap">
    <div className="responseMapHeader">
      <div><p className="eyebrow">SHARED 500 M GRID · 2D SCENARIO VIEW</p><strong>Evacuation corridors and simulated deployment</strong></div>
      <small>Top 40 population flows shown · lines are model routes, not observed GPS tracks</small>
    </div>
    <svg className="responseMap" viewBox="0 0 290 290" role="img" aria-label="Scenario evacuation corridors and simulated firefighting resource deployment on the Paradise grid">
      <defs>
        <pattern id="response-grid" width="10" height="10" patternUnits="userSpaceOnUse">
          <path d="M 10 0 L 0 0 0 10" fill="none" stroke="rgba(228,238,230,.07)" strokeWidth=".5" />
        </pattern>
      </defs>
      <rect width="290" height="290" rx="6" fill="rgba(4,18,12,.72)" />
      <rect width="290" height="290" fill="url(#response-grid)" />
      {flows.map((flow) => {
        const points = flow.path_cell_ids.map(cellPoint).filter(Boolean);
        return <polyline key={`flow-${flow.cell_id}`} points={points.map((point) => `${point.x},${point.y}`).join(" ")} fill="none" stroke="#7fc79a" strokeOpacity={Math.min(.72, .12 + flow.assigned_people / 800)} strokeWidth={Math.min(3.5, .5 + flow.assigned_people / 280)} strokeLinecap="round" strokeLinejoin="round" />;
      })}
      {flows.map((flow) => {
        const point = cellPoint(flow.cell_id);
        return point && <circle key={`origin-${flow.cell_id}`} cx={point.x} cy={point.y} r={Math.min(4, 1 + flow.population / 350)} fill="#b7e3c4" fillOpacity=".72"><title>{flow.cell_id}: {number(flow.population)} synthetic people</title></circle>;
      })}
      {unassigned.map((flow) => {
        const point = cellPoint(flow.cell_id);
        return point && <circle key={`unassigned-${flow.cell_id}`} cx={point.x} cy={point.y} r="3" fill="#d7a84b"><title>{flow.cell_id}: {number(flow.unassigned_people)} unaccommodated</title></circle>;
      })}
      {(detail.shelters || []).map((shelter) => {
        const point = cellPoint(shelter.cell_id);
        return point && <rect key={shelter.id} x={point.x - 4} y={point.y - 4} width="8" height="8" rx="1" fill="#f0d899" stroke="#553b15" strokeWidth="1"><title>{shelter.label}</title></rect>;
      })}
      {assignments.map((item) => {
        const home = cellPoint(item.home_cell_id);
        const target = cellPoint(item.target_cell_id);
        return home && target && <g key={`resource-${item.resource_id}`}>
          <line x1={home.x} y1={home.y} x2={target.x} y2={target.y} stroke="#7fb8d8" strokeWidth="1.2" strokeDasharray="4 3" strokeOpacity=".85" />
          <circle cx={target.x} cy={target.y} r="3" fill="#b05a24" stroke="#ffd3b8" strokeWidth=".7"><title>{item.label} → {item.target_cell_id}</title></circle>
        </g>;
      })}
    </svg>
    <div className="responseLegend"><span><i className="flow" /> synthetic evacuation flow</span><span><i className="unassigned" /> unaccommodated origin</span><span><i className="shelter" /> scenario reception exit</span><span><i className="resource" /> simulated unit deployment</span></div>
  </div>;
}

export default function EvacuationPanel() {
  const [responsePane, setResponsePane] = useState("timing");
  const [config, setConfig] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [selectedId, setSelectedId] = useState("late");
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [includeHazard, setIncludeHazard] = useState(true);
  const [resources, setResources] = useState(null);
  const [strategy, setStrategy] = useState("exposure_weighted");
  const [resourceLoading, setResourceLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    get("/api/v1/paradise/response/config")
      .then((data) => { if (active) setConfig(data); })
      .catch((cause) => { if (active) setError(cause.message); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    post("/api/v1/paradise/evacuation/compare", { include_fire_hazard: includeHazard })
      .then((data) => {
        if (!active) return;
        setComparison(data);
        if (!data.scenarios.some((scenario) => scenario.id === selectedId)) {
          setSelectedId(data.scenarios[0]?.id || "late");
        }
      })
      .catch((cause) => { if (active) setError(cause.message); });
    return () => { active = false; };
  }, [includeHazard]);

  const selectedScenario = comparison?.scenarios.find((scenario) => scenario.id === selectedId) || comparison?.scenarios[0];

  useEffect(() => {
    if (!selectedScenario) return undefined;
    let active = true;
    setDetailLoading(true);
    post("/api/v1/paradise/evacuation/simulate", {
      order_at_utc: selectedScenario.order_at_utc,
      include_fire_hazard: includeHazard,
    })
      .then((data) => { if (active) setDetail(data); })
      .catch((cause) => { if (active) setError(cause.message); })
      .finally(() => { if (active) setDetailLoading(false); });
    return () => { active = false; };
  }, [selectedScenario?.order_at_utc, includeHazard]);

  const resourceAt = useMemo(
    () => comparison?.scenarios.find((scenario) => scenario.id === "late")?.order_at_utc || "2018-11-08T19:50:00Z",
    [comparison],
  );

  useEffect(() => {
    if (!resourceAt) return undefined;
    let active = true;
    setResourceLoading(true);
    post("/api/v1/paradise/resources/simulate", {
      at_utc: resourceAt,
      lead_minutes: 120,
      strategy,
    })
      .then((data) => { if (active) setResources(data); })
      .catch((cause) => { if (active) setError(cause.message); })
      .finally(() => { if (active) setResourceLoading(false); });
    return () => { active = false; };
  }, [resourceAt, strategy]);

  if (error) {
    return <section className="evac panel" aria-label="Evacuation and resources"><p className="prError" role="alert">{error}</p></section>;
  }
  if (!comparison || !config) {
    return <section className="evac panel" aria-label="Evacuation and resources"><p className="prLoading">Running the simulated evacuation scenarios…</p></section>;
  }

  const shelters = detail?.shelters || selectedScenario?.shelters || [];
  const summary = detail?.summary || selectedScenario?.summary;

  return <section className="evac panel" aria-label="Simulated evacuation and firefighting resources">
    <div className="prSectionHeader">
      <div>
        <p className="eyebrow">SIMULATED RESIDENTS · SIMULATED RESOURCES</p>
        <h2>Evacuation timing and response trade-offs</h2>
        <p className="prSectionLead">Residents are synthetic agents generated from aggregated ACS cell population. Vehicles, shelters and firefighting units are scenario assumptions. Nothing here is an observed evacuation, traffic record, resource location or rescue outcome.</p>
      </div>
      <span className="prStatusChip scenario">Scenario only</span>
    </div>

    <nav className="subNav compact" aria-label="Response simulation views">{[["timing", "Evacuation timing"], ["corridors", "Evacuation corridors"], ["resources", "Firefighting resources"]].map(([id, label]) => <button key={id} className={responsePane === id ? "active" : ""} aria-pressed={responsePane === id} onClick={() => setResponsePane(id)}>{label}</button>)}</nav>
    <div className="evacControls">
      <label className="evacToggle"><input type="checkbox" checked={includeHazard} onChange={(event) => setIncludeHazard(event.target.checked)} /> Include predicted fire hazard</label>
      <span className="evacControlNote">{includeHazard ? "Fire arrival is the uncalibrated forecast at each order time. Early order times have no FIRMS forecast; their hazard is not modelled, which is not evidence of safety." : "Hazard is disabled for a pure order-time and capacity comparison. This is not evidence of safety."}</span>
    </div>

    <div className="evacOrderSwitch" role="group" aria-label="Evacuation order time">
      {comparison.scenarios.map((scenario) => <button key={scenario.id} className={scenario.id === selectedId ? "active" : ""} onClick={() => setSelectedId(scenario.id)}>
        <strong>{scenario.label}</strong>
        <small>{formatLocal(scenario.order_at_utc)} · {hazardLabel(scenario.fire_hazard)}</small>
      </button>)}
    </div>

    <div className="evacGrid" hidden={responsePane !== "timing"}>
      <div className="evacCard">
        <div className="evacCardTop"><div><p className="eyebrow">ORDER-TIME COMPARISON</p><strong>Order time changes scenario outputs</strong></div><span className="prStatusChip muted">same seed</span></div>
        <div className="evacTableWrap">
          <table className="evacTable">
            <thead><tr><th>Order</th><th>Pre-left</th><th>Evacuated</th><th>Trapped</th><th>Unaccommodated</th><th>Clearance</th><th>Congestion</th><th>Hazard</th></tr></thead>
            <tbody>
              {comparison.scenarios.map((scenario) => <tr key={scenario.id} className={scenario.id === selectedId ? "active" : ""}>
                <td>{scenario.id}</td>
                <td>{number(scenario.summary.pre_evacuated_people)}</td>
                <td>{number(scenario.summary.evacuated_people)}</td>
                <td>{number(scenario.summary.trapped_people)}</td>
                <td>{number(scenario.summary.unaccommodated_people)}</td>
                <td>{scenario.summary.clearance_status === "complete" ? `${scenario.summary.clearance_minutes} min` : "incomplete"}</td>
                <td>{scenario.summary.congestion_index ?? "—"}</td>
                <td><span className={`evacHazard ${scenario.fire_hazard.status}`}>{hazardLabel(scenario.fire_hazard)}</span></td>
              </tr>)}
            </tbody>
          </table>
        </div>
        <p className="evacNote">The assumed pre-evacuation share reduces demand in later scenarios, so this table is a scenario comparison rather than a causal estimate of an evacuation order. Only the 11:50 scenario has a FIRMS-seeded fire forecast. Zero trapped people in the earlier rows means “hazard not modelled”, not “safe”. “Incomplete” means at least one modelled person did not reach a reception area successfully.</p>
      </div>

      <div className="evacCard">
        <div className="evacCardTop"><div><p className="eyebrow">SELECTED ORDER · {selectedScenario?.label}</p><strong>{detailLoading ? "Running…" : summary ? `${number(summary.evacuated_people)} evacuated` : "No detail"}</strong></div><span className={`evacHazard ${selectedScenario?.fire_hazard.status}`}>{hazardLabel(selectedScenario?.fire_hazard)}</span></div>
        <EvacuationChart timeline={detail?.timeline || []} />
        <div className="evacStats">
          <div><small>People at risk</small><strong>{number(summary?.population_at_risk)}</strong></div>
          <div><small>Evacuated</small><strong>{number(summary?.evacuated_people)}</strong></div>
          <div><small>Trapped</small><strong>{number(summary?.trapped_people)}</strong></div>
          <div><small>Unaccommodated</small><strong>{number(summary?.unaccommodated_people)}</strong></div>
          <div><small>Not cleared</small><strong>{number(summary?.un_evacuated_people)}</strong></div>
          <div><small>Clearance</small><strong>{summary?.clearance_status === "complete" ? `${summary.clearance_minutes} min` : "Incomplete"}</strong></div>
          <div><small>Last successful arrival</small><strong>{summary?.last_successful_arrival_minutes == null ? "—" : `${summary.last_successful_arrival_minutes} min`}</strong></div>
          <div><small>Congestion index</small><strong>{summary?.congestion_index ?? "—"}</strong></div>
        </div>
        <div className="evacShelters">
          {shelters.map((shelter) => {
            const ratio = shelter.capacity ? Math.min(1, shelter.peak_occupancy / shelter.capacity) : 0;
            return <div className="evacShelter" key={shelter.id}>
              <div><strong>{shelter.label}</strong><small>{shelter.outside_grid ? `Off-grid reception, ${shelter.reception_distance_km} km / +${shelter.off_grid_minutes} min` : "In-grid"}</small></div>
              <div className="evacBar"><i style={{ width: `${ratio * 100}%` }} /><span>{number(shelter.peak_occupancy)} / {number(shelter.capacity)}</span></div>
              <small>assigned {number(shelter.assigned_people)} · unaccommodated {number(shelter.unaccommodated_people)}</small>
            </div>;
          })}
        </div>
        {detail && <details className="prAssumptions"><summary>Simulation assumptions</summary><ul>{detail.assumptions.map((item) => <li key={item}>{item}</li>)}</ul><p>{detail.limitations.join(" ")}</p></details>}
        {detail && <small className="evacIdentity">Simulation {detail.simulation_id} · model {detail.model_version} · data {detail.data_version}</small>}
      </div>
    </div>

    <div hidden={responsePane !== "corridors"}><ResponseFlowMap detail={detail} resources={resources} /></div>

    <div className="evacResources" hidden={responsePane !== "resources"}>
      <div className="evacCardTop"><div><p className="eyebrow">SIMULATED FIREFIGHTING RESOURCES</p><strong>Exposure-weighted vs nearest-first</strong></div><span className="prStatusChip scenario">Scenario only</span></div>
      <div className="evacStrategySwitch" role="group" aria-label="Resource allocation strategy">
        {[["exposure_weighted", "Exposure-weighted"], ["nearest_first", "Nearest-first"], ["none", "No action baseline"]].map(([id, label]) => <button key={id} className={strategy === id ? "active" : ""} onClick={() => setStrategy(id)}>{label}</button>)}
      </div>
      {resourceLoading && <p className="prCardMuted">Running resource allocation…</p>}
      {resources?.status === "no_forecast" ? <p className="prCardMuted">{resources.reason}</p> : resources && <>
        <div className="evacStats">
          <div><small>Resources used</small><strong>{resources.summary.resources_used} / {config.resources.resources.length}</strong></div>
          <div><small>Mean response</small><strong>{resources.summary.mean_response_minutes ?? "—"} min</strong></div>
          <div><small>Protected exposure</small><strong>{number(resources.summary.protected_population)}</strong></div>
          <div><small>High-risk cells</small><strong>{resources.summary.high_risk_cells}</strong></div>
          <div><small>Untreated high-risk</small><strong>{resources.summary.untreated_high_risk_cells}</strong></div>
          <div><small>Water layer</small><strong className="missing">Missing</strong></div>
        </div>
        <div className="evacTableWrap">
          <table className="evacTable">
            <thead><tr><th>Unit</th><th>Kind</th><th>Target</th><th>Travel</th><th>Arrival</th><th>Task end</th><th>Protected</th></tr></thead>
            <tbody>
              {(resources.assignments || []).map((item) => <tr key={item.resource_id}>
                <td>{item.label}</td>
                <td>{item.kind}</td>
                <td>{item.target_cell_id || "—"}</td>
                <td>{item.travel_minutes ?? "—"} min</td>
                <td>{item.arrival_minutes ?? "—"} min</td>
                <td>{item.task_end_minutes ?? "—"} min</td>
                <td>{number(item.protected_population)}</td>
              </tr>)}
            </tbody>
          </table>
        </div>
        <p className="evacNote">{resources.water_note} The exposed-weighted strategy protects more aggregated exposure but can respond more slowly; the nearest-first strategy responds faster to nearby cells with less protected exposure. Both are illustrative, not operational plans.</p>
        <details className="prAssumptions"><summary>Resource assumptions and formulas</summary><ul>{resources.assumptions.map((item) => <li key={item}>{item}</li>)}</ul><p>{resources.limitations.join(" ")}</p></details>
        <small className="evacIdentity">Simulation {resources.simulation_id} · model {resources.model_version} · data {resources.data_version}</small>
      </>}
    </div>

    <details className="evacFormulas">
      <summary>Model formulas, parameters and limits</summary>
      <div className="evacFormulaGrid">
        <div><small>EVACUATION DEMAND</small><p>vehicles = population × vehicle_ownership / household_size; walkers = population × walking_share. A scenario pre-evacuation share is removed before the order time.</p></div>
        <div><small>DEPARTURE AND ROUTES</small><p>departure delay ~ lognormal(median 25 min, σ 0.55). Each road cell is a graph node; a platoon moves at most one cell per simulated minute along its shortest road path.</p></div>
        <div><small>CONGESTION</small><p>Edges have assumed hourly capacity from 2025 TIGER road length and class. Shared edge capacity creates queues. Congestion index = simulated vehicle-minutes / free-flow vehicle-minutes.</p></div>
        <div><small>SHELTERS</small><p>Two off-grid scenario reception areas (12,000 and 9,000 people). They are not official shelters. Occupancy is capped; excess demand is unaccommodated.</p></div>
        <div><small>RESOURCE RANKING</small><p>Exposure-weighted score = predicted probability × (cell population + 100). Nearest-first ranks by road travel time. Aircraft use straight-line distance at 220 km/h.</p></div>
        <div><small>LIMITS</small><p>No real resident locations, vehicle counts, traffic, closures, shelter status, resource positions or outcomes. Fire arrival is an uncalibrated prediction. Not for operational use.</p></div>
      </div>
    </details>
  </section>;
}
