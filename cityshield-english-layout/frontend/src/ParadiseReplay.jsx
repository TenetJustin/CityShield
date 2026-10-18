import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import ParadiseGridMap2D from "./ParadiseGridMap2D.jsx";
import EvaluationPanel from "./EvaluationPanel.jsx";
import EvacuationPanel from "./EvacuationPanel.jsx";
import { riskColor } from "./riskVisual.js";

const ParadiseGridScene3D = lazy(() => import("./ParadiseGridScene3D.jsx"));
const API = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");

const SCENARIOS = [
  { id: "baseline", label: "Baseline model", detail: "Assumed NE wind, default fuel, no suppression", payload: { name: "baseline" } },
  { id: "wind_shift", label: "Wind shift +45° ×1.6", detail: "What-if, not a historical wind record", payload: { name: "wind_shift", wind_speed_multiplier: 1.6, wind_direction_delta_deg: 45 } },
  { id: "suppression", label: "Suppression 35%", detail: "Illustrative effect, not an actual response", payload: { name: "suppression", suppression_effectiveness: 0.35 } },
];

const LAYER_LABELS = {
  prediction: "Prediction ≥50%",
  observed: "Observed cells",
  hotspots: "New hotspots",
  roads: "Roads",
  population: "Population bar",
};

function formatUtc(value) {
  if (!value) return "—";
  return new Date(value).toISOString().slice(0, 16).replace("T", " ") + " UTC";
}

function formatLocal(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-US", {
    timeZone: "America/Los_Angeles",
    dateStyle: "medium",
    timeStyle: "short",
  }) + " PT";
}

function minutesBetween(left, right) {
  return Math.round((new Date(right).getTime() - new Date(left).getTime()) / 60000);
}

async function getJson(path, signal) {
  const response = await fetch(`${API}${path}`, { signal });
  if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
  return response.json();
}

function riskLabel(probability) {
  if (probability >= 0.6) return "High";
  if (probability >= 0.3) return "Elevated";
  if (probability >= 0.1) return "Watch";
  return "Low";
}

export default function ParadiseReplay() {
  const [replayPane, setReplayPane] = useState("terrain");
  const [grid, setGrid] = useState(null);
  const [geography, setGeography] = useState(null);
  const [replay, setReplay] = useState(null);
  const [evaluation, setEvaluation] = useState(null);
  const [config, setConfig] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [spatialView, setSpatialView] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get("view");
    return ["map", "scene", "split"].includes(requested) ? requested : "map";
  });
  const [sceneFailed, setSceneFailed] = useState(false);
  const [layers, setLayers] = useState({ prediction: true, observed: true, hotspots: true, roads: true, population: true });
  const [selectedCell, setSelectedCell] = useState(null);
  const [leadMode, setLeadMode] = useState("next");
  const [manualLead, setManualLead] = useState(60);
  const [scenarioId, setScenarioId] = useState("baseline");
  const [forecast, setForecast] = useState(null);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [forecastError, setForecastError] = useState("");
  const forecastAbort = useRef(null);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setLoading(true);
    Promise.all([
      getJson("/api/v1/paradise/grid", controller.signal),
      getJson("/api/v1/paradise/geography", controller.signal),
      getJson("/api/v1/paradise/replay", controller.signal),
      getJson("/api/v1/paradise/evaluation", controller.signal),
      getJson("/api/v1/paradise/replay/config", controller.signal),
    ])
      .then(([gridData, geographyData, replayData, evaluationData, configData]) => {
        if (!active) return;
        setGrid(gridData);
        setGeography(geographyData);
        setReplay(replayData);
        setEvaluation(evaluationData);
        setConfig(configData);
        const firstObservation = replayData.frames.findIndex((frame) => frame.observation_count > 0);
        setFrameIndex(firstObservation >= 0 ? firstObservation : 0);
        setError("");
      })
      .catch((cause) => {
        if (active && cause.name !== "AbortError") setError(cause.message);
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, []);

  const frames = replay?.frames || [];
  const frame = frames[frameIndex] || null;
  const nextObservation = useMemo(
    () => frames.slice(frameIndex + 1).find((item) => item.observation_count > 0) || null,
    [frames, frameIndex],
  );
  const previousObservation = useMemo(
    () => [...frames.slice(0, frameIndex)].reverse().find((item) => item.observation_count > 0) || null,
    [frames, frameIndex],
  );
  const leadMinutes = useMemo(() => {
    if (leadMode === "next" && nextObservation && frame) {
      return Math.max(10, Math.min(720, minutesBetween(frame.at_utc, nextObservation.at_utc)));
    }
    return manualLead;
  }, [leadMode, nextObservation, frame, manualLead]);
  const scenario = SCENARIOS.find((item) => item.id === scenarioId) || SCENARIOS[0];

  useEffect(() => {
    if (!frame) return;
    if (!frame.observation_count) {
      forecastAbort.current?.abort();
      setForecast(null);
      setForecastLoading(false);
      setForecastError("");
      return undefined;
    }
    forecastAbort.current?.abort();
    const controller = new AbortController();
    forecastAbort.current = controller;
    setForecastLoading(true);
    setForecastError("");
    const params = new URLSearchParams({
      at: frame.at_utc,
      lead_minutes: String(Math.round(leadMinutes)),
      threshold: "0.5",
      ...Object.fromEntries(Object.entries(scenario.payload).map(([key, value]) => [key, String(value)])),
    });
    getJson(`/api/v1/paradise/forecast?${params.toString()}`, controller.signal)
      .then((data) => { if (!controller.signal.aborted) setForecast(data); })
      .catch((cause) => {
        if (cause.name === "AbortError") return;
        setForecast(null);
        setForecastError(cause.message);
      })
      .finally(() => { if (!controller.signal.aborted) setForecastLoading(false); });
    return () => controller.abort();
  }, [frame, leadMinutes, scenario]);

  useEffect(() => {
    if (!playing || !frames.length) return undefined;
    if (frameIndex >= frames.length - 1) {
      setPlaying(false);
      return undefined;
    }
    const timer = window.setTimeout(() => setFrameIndex((value) => Math.min(value + 1, frames.length - 1)), 1900 / speed);
    return () => window.clearTimeout(timer);
  }, [playing, speed, frameIndex, frames.length]);

  const handleSceneUnavailable = useCallback(() => {
    setSceneFailed(true);
    setSpatialView("map");
  }, []);

  const evaluationWindow = useMemo(() => {
    if (!evaluation || !frame) return null;
    return evaluation.windows.find((window) => window.from_utc === frame.at_utc) || null;
  }, [evaluation, frame]);

  const observedCells = useMemo(() => new Set(frame?.cumulative_detected_cells || []), [frame]);
  const predictedCells = useMemo(
    () => new Map((forecast?.cells || []).map((cell) => [cell.cell_id, cell])),
    [forecast],
  );
  const selected = useMemo(
    () => grid?.cells.find((cell) => cell.id === selectedCell) || null,
    [grid, selectedCell],
  );
  const selectedPrediction = selectedCell ? predictedCells.get(selectedCell) : null;
  const newHotspots = frame?.new_detections?.filter((item) => item.cell_id).length || 0;
  const predictedNew = forecast?.cells?.filter((cell) => cell.newly_predicted) || [];
  const nextNewCells = useMemo(() => {
    if (!nextObservation || !frame) return new Set();
    const before = new Set(frame.cumulative_detected_cells);
    return new Set(nextObservation.hotspot_cells.filter((cellId) => !before.has(cellId)));
  }, [nextObservation, frame]);
  const nextMatched = useMemo(
    () => [...nextNewCells].filter((cellId) => predictedCells.get(cellId)?.newly_predicted).length,
    [nextNewCells, predictedCells],
  );

  const jumpToObservation = (direction) => {
    if (!frames.length) return;
    if (direction < 0) {
      setFrameIndex(previousObservation ? frames.indexOf(previousObservation) : 0);
    } else {
      setFrameIndex(nextObservation ? frames.indexOf(nextObservation) : frames.length - 1);
    }
  };

  if (loading) {
    return <section className="prReplay panel" aria-label="Camp Fire replay"><p className="prLoading">Loading the real Camp Fire replay, shared grid and evaluation…</p></section>;
  }
  if (error) {
    return <section className="prReplay panel" aria-label="Camp Fire replay"><p className="prError" role="alert">{error}</p></section>;
  }
  if (!grid || !replay || !frame) {
    return <section className="prReplay panel" aria-label="Camp Fire replay"><p className="prError">The real replay package is unavailable.</p></section>;
  }

  const frameSourceLabel = frame.observation_count
    ? "NASA FIRMS observed"
    : frame.data_status === "verified-window"
      ? "NIST verified window"
      : "No spatial observation";
  const isNistOnly = !frame.observation_count && Boolean(frame.nist_window);
  const forecastMessage = forecast?.status === "predicted" ? null : forecast?.reason;
  const comparisonEvidence = scenarioId === "baseline" ? evaluationWindow : null;

  return <section className="prReplay panel" id="paradise-replay" aria-label="Camp Fire real-data replay">
    <div className="prSectionHeader">
      <div>
        <p className="eyebrow">CAMP FIRE 2018 · REAL OBSERVATION REPLAY</p>
        <h2>Real detections, one shared grid, an honest forecast</h2>
        <p className="prSectionLead">FIRMS active-fire detections drive the timeline. NIST contributes verified time windows only. The forecast uses nothing after its issue time. Simulated residents and resources are added in a separate, labelled panel.</p>
      </div>
      <div className="prHeaderActions">
        <span className={`prStatusChip ${isNistOnly ? "nist" : "observed"}`}>{frameSourceLabel}</span>
        <span className="prStatusChip muted">Data {replay.data_version}</span>
      </div>
    </div>

    <nav className="subNav" aria-label="Replay workspace">{[["terrain", "01", "Historical replay"], ["evaluation", "02", "Model evaluation"], ["response", "03", "Response simulation"]].map(([id, n, label]) => <button key={id} className={replayPane === id ? "active" : ""} aria-pressed={replayPane === id} onClick={() => setReplayPane(id)}><small>{n}</small>{label}</button>)}</nav>
    <div className="replayTerrainPane" hidden={replayPane !== "terrain"}>
    <div className="prTimelineBar">
      <div className="prTimelineTop">
        <div>
          <strong>{frame.at_label}</strong>
          <small>{formatUtc(frame.at_utc)} · {frame.observation_count ? `${frame.observation_count} new detections` : "no new detections"}</small>
        </div>
        <div className="prTimelineMeta">
          {frame.gap_since_previous_minutes != null && <span className={frame.gap_since_previous_minutes > 90 ? "gap" : ""}>gap +{Math.round(frame.gap_since_previous_minutes)} min</span>}
          <span>{frameIndex + 1} / {frames.length}</span>
        </div>
      </div>
      <div className="prTimelineControls">
        <button className="secondaryButton prSmallButton" onClick={() => jumpToObservation(-1)} disabled={!previousObservation} aria-label="Previous observation">⏮ Obs</button>
        <button className="playButton" onClick={() => setPlaying((value) => !value)} aria-label={playing ? "Pause replay" : "Play replay"}>{playing ? "Ⅱ" : "▶"}</button>
        <button className="secondaryButton prSmallButton" onClick={() => jumpToObservation(1)} disabled={!nextObservation} aria-label="Next observation">Obs ⏭</button>
        <div className="prSpeed" role="group" aria-label="Replay speed">{[[0.5, "0.5×"], [1, "1×"], [2, "2×"], [4, "4×"]].map(([value, label]) => <button key={value} className={speed === value ? "active" : ""} onClick={() => setSpeed(value)}>{label}</button>)}</div>
        <input
          className="prScrubber"
          type="range"
          min="0"
          max={Math.max(0, frames.length - 1)}
          step="1"
          value={frameIndex}
          onChange={(event) => { setPlaying(false); setFrameIndex(Number(event.target.value)); }}
          aria-label="Replay frame"
        />
      </div>
      <div className="prFrameStrip" role="list" aria-label="Replay frames">
        {frames.map((item, index) => <button
          key={item.id}
          role="listitem"
          className={`${index === frameIndex ? "active" : ""} ${item.observation_count ? "observation" : "nist"}`}
          onClick={() => { setPlaying(false); setFrameIndex(index); }}
          title={`${item.at_label} · ${item.label}`}
        >{item.observation_count ? `${item.observation_count} det` : "NIST"}</button>)}
      </div>
    </div>

    <div className="prBody">
      <div className="prViewer">
        <div className="prViewerToolbar">
          <div className="prViewSwitch" role="group" aria-label="Spatial view">
            {[["map", "2D map"], ["scene", "3D terrain"], ["split", "Both"]].map(([id, label]) => <button key={id} type="button" className={spatialView === id ? "active" : ""} aria-pressed={spatialView === id} onClick={() => setSpatialView(id)} disabled={id !== "map" && sceneFailed}>{label}</button>)}
          </div>
          <div className="prLayerBar" aria-label="Map layers">
            {Object.entries(LAYER_LABELS).map(([id, label]) => <button key={id} className={layers[id] ? "active" : ""} aria-pressed={layers[id]} onClick={() => setLayers((current) => ({ ...current, [id]: !current[id] }))}><i />{label}</button>)}
          </div>
        </div>
        {sceneFailed && <p className="prSceneFailedNote">3D graphics are unavailable on this device; the 2D map remains active.</p>}
        <div className={spatialView === "split" ? "prSpatial split" : "prSpatial"}>
          {spatialView !== "scene" && <ParadiseGridMap2D grid={grid} geography={geography} frame={frame} forecast={forecast} selectedCell={selectedCell} onSelect={setSelectedCell} layers={layers} />}
          {spatialView !== "map" && <Suspense fallback={<div className="prSceneLoading">Loading the 3D terrain view…</div>}><ParadiseGridScene3D grid={grid} geography={geography} frame={frame} forecast={forecast} selectedCell={selectedCell} onSelect={setSelectedCell} layers={layers} onUnavailable={handleSceneUnavailable} /></Suspense>}
        </div>
        <div className="prControlRow">
          <div className="prLeadControl"><small>FORECAST LEAD</small><button className={leadMode === "next" ? "active" : ""} onClick={() => setLeadMode("next")} disabled={!nextObservation}>{nextObservation ? `Next observation (${minutesBetween(frame.at_utc, nextObservation.at_utc)} min)` : "No later snapshot"}</button>{[30, 60, 120].map((value) => <button key={value} className={leadMode === "manual" && manualLead === value ? "active" : ""} onClick={() => { setLeadMode("manual"); setManualLead(value); }}>+{value}</button>)}</div>
          <label className="prScenarioControl"><small>FORECAST SCENARIO (WHAT-IF)</small><select value={scenarioId} onChange={(event) => setScenarioId(event.target.value)}>{SCENARIOS.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        </div>
        <div className="prLegend">
          <span><i className="observed" />Observed cell (FIRMS proxy)</span>
          <span><i className="hotspot" />New hotspot</span>
          <span><i className="low" />Predicted low</span>
          <span><i className="elevated" />Elevated</span>
          <span><i className="high" />High</span>
          <span><i className="population" />Population bar</span>
        </div>
        <p className="prDisclaimer">500 m cells. FIRMS detections are active-fire points, not a perimeter or burn scar. The 3D height combines coarse elevation with predicted risk and is a viewing aid, not a fire-height or fire-behaviour model.</p>
      </div>

      <aside className="prSidebar">
        <div className="prCard">
          <p className="eyebrow">CURRENT OBSERVATION</p>
          <div className="prCardMain"><strong>{frame.observation_count ? `${frame.observation_count} detections` : "No spatial detections"}</strong><span className={`prStatusChip ${isNistOnly ? "nist" : "observed"}`}>{frameSourceLabel}</span></div>
          <dl className="prFacts">
            <div><dt>Time</dt><dd>{formatLocal(frame.at_utc)}</dd></div>
            <div><dt>UTC</dt><dd>{formatUtc(frame.at_utc)}</dd></div>
            <div><dt>Observed cells</dt><dd>{observedCells.size} of {grid.cell_count}</dd></div>
            <div><dt>Outside grid</dt><dd>{frame.outside_grid_count} detections</dd></div>
            <div><dt>Weather</dt><dd className="missing">Historical record missing</dd></div>
            <div><dt>Latency</dt><dd>Acquisition time only; processing delay unknown</dd></div>
          </dl>
          {frame.nist_window && <p className="prNistNote">NIST window {frame.nist_window.id}: time verified, spatial symbols not digitized. No NIST cells are drawn.</p>}
          {isNistOnly && <p className="prNistNote strong">This frame is a NIST time window, not a mapped observation. The first FIRMS snapshot is 2018-11-08 11:50 PT.</p>}
        </div>

        <div className="prCard">
          <p className="eyebrow">PREDICTION · +{Math.round(leadMinutes)} MIN</p>
          {!frame.observation_count ? <p className="prCardMuted">No forecast: there are no mapped observations at this time, and the model does not fabricate a fire.</p> : forecastLoading ? <p className="prCardMuted">Computing the deterministic ensemble…</p> : forecastError ? <p className="prError" role="alert">{forecastError}</p> : forecast?.status !== "predicted" ? <p className="prCardMuted">{forecastMessage || "No forecast available."}</p> : <>
            <div className="prCardMain"><strong>{forecast.summary.predicted_new_cells} new cells</strong><span className="prStatusChip predicted">Predicted</span></div>
            <dl className="prFacts">
              <div><dt>Predicted exposure</dt><dd>{Math.round(forecast.summary.predicted_new_population).toLocaleString()} people</dd></div>
              <div><dt>Seed cells</dt><dd>{forecast.summary.seed_cells}</dd></div>
              <div><dt>Max new-cell probability</dt><dd>{Math.round(Math.max(0, ...forecast.cells.filter((cell) => !cell.seed).map((cell) => cell.probability)) * 100)}%</dd></div>
              <div><dt>Members</dt><dd>{forecast.summary.members} · {forecast.summary.step_minutes} min steps</dd></div>
              <div><dt>Weather</dt><dd className="scenario">Scenario assumption: NE 12 m/s, 20% RH</dd></div>
              <div><dt>Scenario</dt><dd>{scenario.label}</dd></div>
            </dl>
            <details className="prAssumptions"><summary>Model assumptions and limits</summary><ul>{forecast.assumptions.map((item) => <li key={item}>{item}</li>)}</ul><p>{forecast.limitations.join(" ")}</p></details>
          </>}
        </div>

        <div className="prCard">
          <p className="eyebrow">PREDICTED VS NEXT OBSERVATION</p>
          {!nextObservation ? <p className="prCardMuted">No later FIRMS snapshot in this replay window.</p> : <>
            <div className="prCardMain"><strong>{nextNewCells.size} new observed cells</strong><span className="prStatusChip observed">Next snapshot</span></div>
            <dl className="prFacts">
              <div><dt>Next snapshot</dt><dd>{formatLocal(nextObservation.at_utc)}</dd></div>
              <div><dt>Lead</dt><dd>{minutesBetween(frame.at_utc, nextObservation.at_utc)} min</dd></div>
              <div><dt>Matched predictions</dt><dd>{nextMatched} of {nextNewCells.size}</dd></div>
            </dl>
            {scenarioId !== "baseline" ? <p className="prCardMuted">This what-if scenario is not scored. The evaluation below is for the frozen baseline model only.</p> : comparisonEvidence?.current ? <>
              <div className="prMiniMetrics">
                <span><b>{comparisonEvidence.current.precision ?? "—"}</b>precision</span>
                <span><b>{comparisonEvidence.current.recall ?? "—"}</b>recall</span>
                <span><b>{comparisonEvidence.current.iou ?? "—"}</b>IoU</span>
              </div>
              <p className={`prEvidenceLine ${comparisonEvidence.evidence.status}`}>{comparisonEvidence.evidence.status === "sufficient" ? "Window meets the configured reporting floor; this is not independent validation." : `Window is below the reporting floor: ${comparisonEvidence.evidence.reasons.join("; ")}`}</p>
            </> : <p className="prCardMuted">No evaluated window matches this frame.</p>}
          </>}
        </div>

        <div className="prCard">
          <p className="eyebrow">SELECTED CELL</p>
          <select className="prCellSelect" value={selectedCell || ""} onChange={(event) => setSelectedCell(event.target.value || null)} aria-label="Select a grid cell">
            <option value="">Choose a cell…</option>
            {grid.cells.map((cell) => <option key={cell.id} value={cell.id}>{cell.id} · {Math.round(cell.population)} people{cell.in_town ? "" : " · outside town"}</option>)}
          </select>
          {!selected ? <p className="prCardMuted">Click a cell on the map or choose one here. Population is area-level ACS exposure, not resident locations.</p> : <>
            <div className="prCardMain"><strong>{selected.id}</strong><span className={`prStatusChip ${selectedPrediction ? "predicted" : observedCells.has(selected.id) ? "observed" : "muted"}`}>{observedCells.has(selected.id) ? "Observed" : selectedPrediction ? "Predicted" : "No fire signal"}</span></div>
            <dl className="prFacts">
              <div><dt>Population</dt><dd>{Math.round(selected.population).toLocaleString()} (±{Math.round(selected.population_moe).toLocaleString()})</dd></div>
              <div><dt>Elevation</dt><dd>{selected.elevation_m} m · slope {selected.slope_deg}°</dd></div>
              <div><dt>Roads</dt><dd>{Math.round(selected.road_length_m)} m{selected.road_names.length ? ` · ${selected.road_names.slice(0, 2).join(", ")}` : ""}</dd></div>
              <div><dt>Prediction</dt><dd>{selectedPrediction ? `${Math.round(selectedPrediction.probability * 100)}% (${riskLabel(selectedPrediction.probability)}) · arrival ${selectedPrediction.arrival_minutes ?? "—"} min` : "No predicted ignition"}</dd></div>
              <div><dt>Fuel</dt><dd className="assumed">Default {selected.fuel_value} · no observed fuel layer</dd></div>
              <div><dt>Water</dt><dd className="missing">Missing</dd></div>
            </dl>
          </>}
        </div>

        <div className="prCard prSourceCard">
          <p className="eyebrow">SOURCE STATUS</p>
          <div className="prSourceList">
            <span><i className="observed" />FIRMS · observed</span>
            <span><i className="nist" />NIST · time window only</span>
            <span><i className="derived" />Population · derived</span>
            <span><i className="assumed" />Fuel · assumed</span>
            <span><i className="missing" />Water/facilities · missing</span>
            <span><i className="scenario" />Weather · scenario assumption</span>
          </div>
          <p className="prCardMuted">Replay {replay.replay_id} · grid {replay.grid_version} · model {forecast?.model_version || config?.config?.forecast?.model_version || "—"}</p>
        </div>
      </aside>
    </div>

    </div>
    <div hidden={replayPane !== "evaluation"}><EvaluationPanel evaluation={evaluation} /></div>
    <div hidden={replayPane !== "response"}><EvacuationPanel /></div>
  </section>;
}
