import React, { Suspense, lazy, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import WildfireMap2D from "./WildfireMap2D.jsx";
import ParadiseData from "./ParadiseData.jsx";
import "./styles.css";

const WildfireScene = lazy(() => import("./WildfireScene.jsx"));

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const HORIZONS = [30, 60, 120];
const REPLAY_TIMES = [0, 30, 60, 120];
const SCENARIOS = [
  { id: "baseline", title: "Current outlook", detail: "No changed assumptions", payload: { name: "baseline" } },
  { id: "wind_shift", title: "Wind turns", detail: "Direction +90°, speed ×1.4", payload: { name: "wind_shift", wind_speed_multiplier: 1.4, wind_direction_delta_deg: 90 } },
  { id: "dry_gust", title: "Dry gust", detail: "Drier air, speed ×1.7", payload: { name: "dry_gust", wind_speed_multiplier: 1.7, humidity_delta_pct: -10 } },
  { id: "suppression_support", title: "More suppression", detail: "Illustrative 35% effect", payload: { name: "suppression_support", suppression_effectiveness: 0.35 } },
];

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
  return payload;
}

const riskAt = (cell, horizon) => cell?.series?.find((point) => point.horizon_minutes === horizon)?.p90 ?? 0;
const riskLevel = (value) => value >= 0.6 ? "High" : value >= 0.3 ? "Elevated" : value >= 0.1 ? "Watch" : "Low";
const formatArea = (value) => value < 1 ? `${Math.round(value * 100)} ha` : `${value.toFixed(2)} km²`;

function App() {
  const [result, setResult] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [worldState, setWorldState] = useState(null);
  const [decision, setDecision] = useState(null);
  const [simulation, setSimulation] = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [delivery, setDelivery] = useState(null);
  const [incident, setIncident] = useState(null);
  const [city, setCity] = useState(null);
  const [sources, setSources] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [audits, setAudits] = useState([]);
  const [horizon, setHorizon] = useState(30);
  const [viewMode, setViewMode] = useState("live");
  const [spatialView, setSpatialView] = useState("map");
  const [replayMinute, setReplayMinute] = useState(0);
  const [layers, setLayers] = useState({ forecast: true, observed: true, hotspots: true, resources: true });
  const [scenario, setScenario] = useState("baseline");
  const [activeStep, setActiveStep] = useState("situation");
  const [selectedCell, setSelectedCell] = useState(null);
  const [streamCount, setStreamCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [resetSignal, setResetSignal] = useState(0);
  const [message, setMessage] = useState("Loading the demonstration");
  const [error, setError] = useState("");
  const [rsiCandidate, setRsiCandidate] = useState(null);
  const eventSource = useRef(null);

  async function refreshSystem() {
    const [ready, cityData, stateData, sourceData, metricData, auditData, deliveryData, incidentData] = await Promise.all([
      api("/api/v1/readiness"), api("/api/v1/city"), api("/api/v1/state"),
      api("/api/v1/sources"), api("/api/v1/metrics"), api("/api/v1/audits?limit=20"),
      api("/api/v1/delivery/readiness"), api("/api/v1/demo/incident"),
    ]);
    setReadiness(ready);
    setCity(cityData);
    setWorldState(stateData);
    setSources(sourceData.sources);
    setMetrics(metricData);
    setAudits([...auditData.records].reverse());
    setDelivery(deliveryData);
    setIncident(incidentData);
  }

  function receiveCompleted(data, count) {
    setResult(data);
    setForecast(data.forecast);
    setDecision(data.decision);
    setSimulation(null);
    setScenario("baseline");
    setHorizon(30);
    setStreamCount(count);
    setSelectedCell(null);
    setRsiCandidate(null);
    setMessage("Forecast ready · review the risk before deciding");
  }

  async function replay() {
    eventSource.current?.close();
    setLoading(true);
    setPlaying(false);
    setError("");
    try {
      await api("/api/v1/demo/reset", { method: "POST" });
      const data = await api("/api/v1/demo/replay", { method: "POST" });
      receiveCompleted(data, data.observations);
      setActiveStep("situation");
      await refreshSystem();
    } catch (value) { setError(value.message); }
    finally { setLoading(false); }
  }

  async function startStream() {
    eventSource.current?.close();
    setLoading(true);
    setPlaying(false);
    setError("");
    setForecast(null);
    setWorldState(null);
    setDecision(null);
    setStreamCount(0);
    setHorizon(30);
    setActiveStep("situation");
    setViewMode("live");
    setMessage("Receiving observations…");
    try {
      await api("/api/v1/demo/reset", { method: "POST" });
      const events = new EventSource(`${API}/api/v1/demo/stream?delay_ms=350`);
      eventSource.current = events;
      events.addEventListener("observation", (event) => {
        const data = JSON.parse(event.data);
        setWorldState(data.state);
        setStreamCount((value) => value + (data.accepted ? 1 : 0));
        setMessage(`Observation received · ${data.observation.kind.replaceAll("_", " ")}`);
      });
      events.addEventListener("complete", async (event) => {
        const data = JSON.parse(event.data);
        receiveCompleted(data, data.forecast.provenance.observation_count);
        setLoading(false);
        setPlaying(true);
        events.close();
        eventSource.current = null;
        try { await refreshSystem(); } catch (value) { setError(value.message); }
      });
      events.onerror = () => {
        setError("The stream stopped. Run the demonstration again.");
        setLoading(false);
        events.close();
        eventSource.current = null;
      };
    } catch (value) { setError(value.message); setLoading(false); }
  }

  async function simulate(id) {
    if (!result?.forecast || loading) return;
    setLoading(true);
    setPlaying(false);
    setError("");
    try {
      if (id === "baseline") { setForecast(result.forecast); setSimulation(null); }
      else {
        const preset = SCENARIOS.find((item) => item.id === id);
        const data = await api("/api/v1/scenarios/simulate", {
          method: "POST", body: JSON.stringify(preset.payload),
        });
        setForecast(data.scenario);
        setSimulation(data);
        const baselineByCell = Object.fromEntries(
          data.baseline.cells.map((cell) => [cell.cell_id, cell]),
        );
        const mostChanged = [...data.scenario.cells].sort((left, right) =>
          Math.abs(riskAt(right, horizon) - riskAt(baselineByCell[right.cell_id], horizon))
          - Math.abs(riskAt(left, horizon) - riskAt(baselineByCell[left.cell_id], horizon))
        )[0];
        if (mostChanged) setSelectedCell(mostChanged.cell_id);
      }
      setScenario(id);
      setMessage(id === "baseline" ? "Current outlook restored" : "Scenario compared with the same evidence snapshot");
      await refreshSystem();
    } catch (value) { setError(value.message); }
    finally { setLoading(false); }
  }

  async function review(approved) {
    if (!decision) return;
    setError("");
    try {
      const updated = await api(`/api/v1/decisions/${decision.decision_run_id}/review`, {
        method: "POST",
        body: JSON.stringify({ approved, reviewer: "Datathon demo commander", note: "Demo review" }),
      });
      setDecision(updated);
      setMessage(approved ? "Recommendation approved for coordination" : "Recommendation rejected");
      await refreshSystem();
    } catch (value) { setError(value.message); }
  }

  async function evaluateRsi() {
    setError("");
    try {
      const candidate = await api("/api/v1/rsi/evaluate", {
        method: "POST",
        body: JSON.stringify({ event_id: "synthetic-demo-001", burned_cells: ["B1", "B2", "A1"] }),
      });
      setRsiCandidate(candidate);
      setMessage("A shadow model candidate was created for review");
      await refreshSystem();
    } catch (value) { setError(value.message); }
  }

  useEffect(() => { replay(); return () => eventSource.current?.close(); }, []);
  useEffect(() => {
    if (!playing) return undefined;
    const timer = window.setInterval(() => {
      const sequence = viewMode === "replay" ? REPLAY_TIMES : HORIZONS;
      const current = viewMode === "replay" ? replayMinute : horizon;
      const index = sequence.indexOf(current);
      if (index >= sequence.length - 1) { setPlaying(false); return; }
      if (viewMode === "replay") setReplayMinute(sequence[index + 1]);
      else setHorizon(sequence[index + 1]);
    }, 1500);
    return () => window.clearInterval(timer);
  }, [playing, viewMode, replayMinute, horizon]);

  const replayFrame = useMemo(() => {
    const frames = incident?.frames || [];
    return [...frames].reverse().find((frame) => frame.minute <= replayMinute) || frames[0] || null;
  }, [incident, replayMinute]);

  const displayHorizon = viewMode === "replay" ? Math.max(30, replayMinute) : horizon;

  const cells = useMemo(() => {
    const observed = new Set(viewMode === "replay" ? replayFrame?.observed_cells || [] : []);
    const hotspots = new Set(viewMode === "replay" ? replayFrame?.hotspot_cells || [] : []);
    const base = forecast
      ? forecast.cells.map((cell) => ({ id: cell.cell_id, ...cell.static, risk: layers.forecast ? riskAt(cell, displayHorizon) : 0 }))
      : Object.entries(worldState?.cells || {}).map(([id, cell]) => ({ id, ...cell.static, risk: layers.forecast ? cell.burning_probability : 0 }));
    return base.map((cell) => ({ ...cell, observed: observed.has(cell.id), hotspot: hotspots.has(cell.id) }));
  }, [forecast, displayHorizon, worldState, viewMode, replayFrame, layers.forecast]);
  const sortedCells = useMemo(() => [...cells].sort((a, b) => b.risk - a.risk), [cells]);
  const selected = cells.find((cell) => cell.id === selectedCell) || sortedCells[0];
  const cellArea = ((city?.model_grid_m || 500) / 1000) ** 2;
  const counts = {
    high: cells.filter((cell) => cell.risk >= 0.6).length,
    elevated: cells.filter((cell) => cell.risk >= 0.3 && cell.risk < 0.6).length,
    watch: cells.filter((cell) => cell.risk >= 0.1 && cell.risk < 0.3).length,
  };
  const footprint = (counts.high + counts.elevated + counts.watch) * cellArea;
  const exposedPopulation = cells.filter((cell) => cell.risk >= 0.3).reduce((sum, cell) => sum + (cell.population || 0), 0);
  const baselineCells = result?.forecast?.cells || [];
  const currentCellForecast = forecast?.cells.find((cell) => cell.cell_id === selected?.id);
  const baselineCellForecast = baselineCells.find((cell) => cell.cell_id === selected?.id);
  const selectedDelta = currentCellForecast && baselineCellForecast
    ? riskAt(currentCellForecast, displayHorizon) - riskAt(baselineCellForecast, displayHorizon) : 0;
  const footprintAt = (minutes) => (forecast?.cells || []).filter((cell) => riskAt(cell, minutes) >= 0.1).length * cellArea;
  const growthRate = displayHorizon === 30 ? null : (footprint - footprintAt(30)) / ((displayHorizon - 30) / 60);
  const observedSet = new Set(replayFrame?.observed_cells || []);
  const predictedSet = new Set(cells.filter((cell) => cell.risk >= 0.3).map((cell) => cell.id));
  const overlapCount = [...observedSet].filter((cellId) => predictedSet.has(cellId)).length;
  const overlapPct = observedSet.size ? Math.round((overlapCount / observedSet.size) * 100) : null;
  const activeResources = useMemo(
    () => (incident?.resources || []).filter((resource) => resource.available_from_minute <= replayMinute),
    [incident, replayMinute],
  );
  const actions = (decision?.actions || []).filter((action) => action.action !== "monitor");
  const headline = activeStep === "situation"
      ? viewMode === "replay" ? `Replaying minute ${replayMinute} · ${replayFrame?.note || "incident evidence"}` : `${counts.high} high-risk cells in the ${horizon}-minute outlook`
    : activeStep === "scenario"
      ? scenario === "baseline" ? "Choose a change to compare with the outlook" : `${SCENARIOS.find((item) => item.id === scenario)?.title} compared with baseline`
      : `${actions.length} areas need a coordination decision`;

  return <main className="appShell">
    <header className="topbar"><div className="brand"><span className="brandMark">C<span>✦</span></span><div><strong>CityShield</strong><small>WILDFIRE DECISION STUDIO</small></div></div><div className="topActions"><div className="modeSwitch" aria-label="Workspace mode"><button className={viewMode === "live" ? "active" : ""} onClick={() => { setViewMode("live"); setPlaying(false); }}>Live outlook</button><button className={viewMode === "replay" ? "active" : ""} onClick={() => { setViewMode("replay"); setReplayMinute(0); setPlaying(false); }}>Incident replay</button></div><span className="modeBadge">{viewMode === "replay" ? "CACHED EXERCISE" : "SYNTHETIC LIVE"} · ADVISORY ONLY</span><button className="primaryButton" onClick={startStream} disabled={loading}>{loading ? "Receiving data…" : "Run live demonstration"}</button></div></header>

    <section className="intro"><div><p className="eyebrow">REAL-TIME AI FOR CRITICAL DECISIONS · IBM LINUXONE</p><h1>See the risk. Test the change.<br /><em>Decide with evidence.</em></h1></div><div className="introAside"><span className="pulseDot" />{message}<small>{streamCount} observations · {forecast?.latency_ms ?? "—"} ms forecast</small></div></section>
    {error && <div className="error" role="alert">{error}</div>}

    <ParadiseData />

    <nav className="stepNav" aria-label="Decision workflow">{[
      { id: "situation", number: "01", title: "Understand risk", detail: "What is changing?" },
      { id: "scenario", number: "02", title: "Test a scenario", detail: "What if conditions shift?" },
      { id: "action", number: "03", title: "Review action", detail: "What should people do?" },
    ].map((step) => <button key={step.id} className={activeStep === step.id ? "stepItem active" : "stepItem"} onClick={() => setActiveStep(step.id)}><b>{step.number}</b><span><strong>{step.title}</strong><small>{step.detail}</small></span></button>)}</nav>

    <section className="workspace"><article className="scenePanel panel"><div className="panelTop"><div><p className="eyebrow">CITY WORLD STATE · LINKED 2D + 3D</p><h2>{headline}</h2></div><button className="textButton" onClick={() => setResetSignal((value) => value + 1)}>Reset 3D view ↗</button></div><div className="viewSelector" role="group" aria-label="Spatial view">{[["map", "2D map"], ["scene", "3D scene"], ["split", "Both views"]].map(([id, label]) => <button key={id} type="button" className={spatialView === id ? "active" : ""} aria-pressed={spatialView === id} onClick={() => setSpatialView(id)}>{label}</button>)}</div><div className="layerBar" aria-label="Map layers">{[
      ["forecast", "Forecast"], ["observed", "Observed edge"], ["hotspots", "Hotspots"], ["resources", "Resources"],
    ].map(([id, label]) => <button key={id} className={layers[id] ? "active" : ""} onClick={() => setLayers((current) => ({ ...current, [id]: !current[id] }))}><i />{label}</button>)}</div>{viewMode === "replay" && <div className="qualityRibbon"><strong>Offline-safe replay</strong><span>{incident?.quality?.label} · actual and predicted states remain visually separate.</span></div>}<div className={spatialView === "split" ? "spatialViews split" : "spatialViews"}>
      {spatialView !== "scene" && <WildfireMap2D cells={cells} selectedCell={selected?.id} onSelect={setSelectedCell} showObserved={viewMode === "replay" && layers.observed} showHotspots={viewMode === "replay" && layers.hotspots} resources={layers.resources && viewMode === "replay" ? activeResources : []} />}
      {spatialView !== "map" && <Suspense fallback={<div className="sceneLoading">Loading 3D view…</div>}><WildfireScene cells={cells} selectedCell={selected?.id} onSelect={setSelectedCell} resetSignal={resetSignal} showObserved={viewMode === "replay" && layers.observed} showHotspots={viewMode === "replay" && layers.hotspots} resources={layers.resources && viewMode === "replay" ? activeResources : []} /></Suspense>}
    </div><div className="timeline"><div className="timelineTop"><strong>{viewMode === "replay" ? "Incident evidence timeline" : "Forecast timeline"}</strong><span>{forecast ? `+${viewMode === "replay" ? replayMinute : horizon} min` : "Receiving live observations"}</span></div><div className="timelineControls"><button className="playButton" onClick={() => { const atEnd = viewMode === "replay" ? replayMinute === 120 : horizon === 120; if (atEnd) { if (viewMode === "replay") setReplayMinute(0); else setHorizon(30); } setPlaying(!playing); }} disabled={!forecast} aria-label={playing ? "Pause timeline" : "Play timeline"}>{playing ? "Ⅱ" : "▶"}</button><div className="timeChoices">{(viewMode === "replay" ? REPLAY_TIMES : HORIZONS).map((value) => <button key={value} className={(viewMode === "replay" ? replayMinute : horizon) === value ? "active" : ""} onClick={() => { setPlaying(false); if (viewMode === "replay") setReplayMinute(value); else setHorizon(value); }} disabled={!forecast}>+{value} min</button>)}</div></div>{viewMode === "replay" && <div className="eventTrack">{(incident?.events || []).map((event) => <span key={`${event.minute}-${event.type}`} className={event.minute <= replayMinute ? "reached" : ""}><i />{event.label}</span>)}</div>}</div><div className="legend"><span><i className="low" /> Low &lt;10%</span><span><i className="watch" /> Watch 10–29%</span><span><i className="elevated" /> Elevated 30–59%</span><span><i className="high" /> High ≥60%</span>{viewMode === "replay" && <><span><i className="observed" /> Observed</span><span><i className="hotspot" /> Hotspot</span></>}</div><p className="disclaimer">Illustrative terrain and synthetic {city?.model_grid_m || 500} m cells. P90 is an uncalibrated model proxy; colored cells are not a fire perimeter or official warning.</p></article>

    <aside className="insightPanel panel">{activeStep === "situation" && <><p className="eyebrow">01 / UNDERSTAND RISK</p><h2>{viewMode === "replay" ? "What did the model see?" : "What needs attention?"}</h2><div className="metricMain"><strong>{formatArea(footprint)}</strong><span>area at Watch risk or higher</span></div><div className="metricPair"><div><strong>{viewMode === "replay" ? `${observedSet.size} cells` : growthRate == null ? "—" : `${formatArea(Math.max(0, growthRate))}/h`}</strong><small>{viewMode === "replay" ? "observed exercise perimeter" : "average area growth since +30 min"}</small></div><div><strong>{viewMode === "replay" ? overlapPct == null ? "—" : `${overlapPct}%` : exposedPopulation.toLocaleString()}</strong><small>{viewMode === "replay" ? "observed cells captured by elevated forecast" : "people in elevated/high cells"}</small></div></div>{viewMode === "replay" && <div className="replaySummary"><span><b>{replayFrame?.hotspot_cells?.length || 0}</b> hotspots</span><span><b>{activeResources.length}</b> active resources</span><span><b>{replayFrame?.weather?.wind_speed || "—"}</b> m/s wind</span></div>}<div className="severityBar" aria-label={`${counts.high} high, ${counts.elevated} elevated, ${counts.watch} watch cells`}><i style={{ flex: counts.high || 0.05 }} /><i style={{ flex: counts.elevated || 0.05 }} /><i style={{ flex: counts.watch || 0.05 }} /></div><p className="countLine">{counts.high} high · {counts.elevated} elevated · {counts.watch} watch</p><div className="sectionDivider" /><p className="eyebrow">SELECTED AREA</p>{selected ? <div className="selectedArea"><div><strong>{selected.id}</strong><span className={`riskBadge ${riskLevel(selected.risk).toLowerCase()}`}>{riskLevel(selected.risk)}</span></div><p>{forecast ? "P90 risk" : "Observed state proxy"} {Math.round(selected.risk * 100)}% · {selected.population?.toLocaleString() || 0} residents · {selected.critical_facilities || 0} critical facilities{selected.observed ? " · observed inside perimeter" : ""}</p></div> : <p>Run the demonstration to inspect an area.</p>}<div className="areaList">{sortedCells.slice(0, 4).map((cell) => <button key={cell.id} className={selected?.id === cell.id ? "active" : ""} onClick={() => setSelectedCell(cell.id)}><span>{cell.id}{cell.observed ? " · observed" : ""}</span><b>{Math.round(cell.risk * 100)}%</b></button>)}</div><button className="nextButton" onClick={() => setActiveStep("scenario")}>Next: test a scenario <span>→</span></button></>}

    {activeStep === "scenario" && <><p className="eyebrow">02 / TEST A SCENARIO</p><h2>Change one assumption</h2><p className="panelLead">Every option uses the same frozen observation snapshot. Select one to see how risk changes.</p><div className="scenarioList">{SCENARIOS.map((item) => <button key={item.id} className={scenario === item.id ? "scenarioCard active" : "scenarioCard"} onClick={() => simulate(item.id)} disabled={loading || !result}><span><strong>{item.title}</strong><small>{item.detail}</small></span><b>{scenario === item.id ? "✓" : "→"}</b></button>)}</div><div className="sectionDivider" /><p className="eyebrow">PAIRED DIFFERENCE · +{displayHorizon} MIN</p><div className="metricMain"><strong>{selectedDelta >= 0 ? "+" : ""}{Math.round(selectedDelta * 100)} pts</strong><span>P90 change in selected cell {selected?.id || "—"}</span></div><p className="comparisonNote">{simulation ? `Scenario run ${simulation.simulation_run_id} · both runs share evidence ${simulation.baseline.evidence_snapshot_id}.` : "Choose a scenario to compare with baseline."}</p><button className="nextButton" onClick={() => setActiveStep("action")}>Next: review action <span>→</span></button></>}

    {activeStep === "action" && <><p className="eyebrow">03 / REVIEW ACTION</p><h2>Human decision queue</h2><p className="panelLead">Recommendations use the frozen baseline forecast. Scenario results inform discussion; they do not silently change the queue.</p><div className="decisionStatus"><span className="pulseDot" />{decision?.status?.replaceAll("_", " ") || "Awaiting forecast"}</div><div className="actionList">{actions.slice(0, 5).map((action) => <div className="actionRow" key={action.cell_id}><b>P{action.priority}</b><div><strong>{action.cell_id} · {action.action.replaceAll("_", " ")}</strong><small>{action.reason}</small></div></div>)}</div>{decision?.status === "pending_human_review" && <div className="reviewButtons"><button className="secondaryButton" onClick={() => review(false)}>Reject</button><button className="primaryButton" onClick={() => review(true)}>Approve for coordination</button></div>}<p className="safetyNote">Approval records a coordination decision. It does not issue an alert, order an evacuation or dispatch responders.</p></>}</aside></section>

    <details className="evidence panel"><summary><span><b>Evidence, data readiness & system details</b><small>Sources, fallbacks, audit trail, model limits and improvement</small></span><span>Expand +</span></summary><div className="deliveryBanner"><div><span className="statusDot pass" /><strong>Competition demo ready</strong><small>Offline replay, forecast, decision and audit paths do not require an external API.</small></div><div><span className={`statusDot ${delivery?.live_city_ready ? "pass" : "blocked"}`} /><strong>{delivery?.live_city_ready ? "Live city feeds ready" : "Live city feeds gated"}</strong><small>{delivery?.city_selected ? "Source checks still required" : "Select a city before claiming live operation"}.</small></div></div><div className="evidenceGrid"><div><p className="eyebrow">DATA SOURCES</p>{sources.map((source) => <div className="evidenceRow" key={source.source_id}><span>{source.source_id}</span><small>{source.ready ? "Live ready" : source.adapter === "implemented" ? "Adapter ready" : "City work"}</small></div>)}</div><div><p className="eyebrow">DELIVERY GATES</p>{(delivery?.gates || []).map((gate) => <div className="gateRow" key={gate.id}><span className={`statusDot ${gate.status}`} /><div><strong>{gate.label}</strong><small>{gate.reason}</small></div></div>)}</div><div><p className="eyebrow">AUDIT TRAIL</p><p className="evidenceSummary">{readiness?.audit?.valid ? "Chain verified" : "Checking"} · {readiness?.audit?.records || 0} records</p>{audits.slice(0, 5).map((record) => <div className="evidenceRow" key={record.hash}><span>{record.event_type.replaceAll("_", " ")}</span><code>{record.hash.slice(0, 8)}</code></div>)}</div><div><p className="eyebrow">CONTROLLED IMPROVEMENT</p><p className="evidenceSummary">Model {forecast?.model_version || "—"}</p><p>A completed event can produce a shadow candidate. Active predictions never change automatically.</p><button className="secondaryButton" onClick={evaluateRsi} disabled={!forecast}>Run demo evaluation</button>{rsiCandidate && <p className="candidateNote">{rsiCandidate.status} · Brier {rsiCandidate.evaluation.brier_score}</p>}</div></div><div className="evidenceFooter"><span>Evidence {forecast?.evidence_snapshot_id || "—"}</span><span>Forecast {forecast?.forecast_run_id || "—"}</span><span>{metrics?.observations_ingested || 0} observations processed</span><span>{delivery?.policy}</span></div></details>
    <footer>CityShield research prototype · Demonstration data only · Built for IBM Z Datathon 2026</footer>
  </main>;
}

createRoot(document.getElementById("root")).render(<App />);
