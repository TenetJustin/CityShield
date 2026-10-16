import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
  return payload;
}

const SCENARIOS = {
  baseline: { name: "baseline" },
  wind_shift: { name: "wind_shift", wind_speed_multiplier: 1.4, wind_direction_delta_deg: 90 },
  dry_gust: { name: "dry_gust", wind_speed_multiplier: 1.7, humidity_delta_pct: -10 },
  suppression_support: { name: "suppression_support", suppression_effectiveness: 0.35 },
};

function App() {
  const [result, setResult] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [decision, setDecision] = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [sources, setSources] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [audits, setAudits] = useState([]);
  const [horizon, setHorizon] = useState(120);
  const [scenario, setScenario] = useState("baseline");
  const [streamCount, setStreamCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("Ready for synthetic replay");
  const [error, setError] = useState("");
  const [rsiCandidate, setRsiCandidate] = useState(null);

  async function refreshSystem() {
    const [ready, sourceData, metricData, auditData] = await Promise.all([
      api("/api/v1/readiness"),
      api("/api/v1/sources"),
      api("/api/v1/metrics"),
      api("/api/v1/audits?limit=20"),
    ]);
    setReadiness(ready);
    setSources(sourceData.sources);
    setMetrics(metricData);
    setAudits(auditData.records.reverse());
  }

  async function replay() {
    setLoading(true);
    setError("");
    try {
      await api("/api/v1/demo/reset", { method: "POST" });
      const data = await api("/api/v1/demo/replay", { method: "POST" });
      setResult(data);
      setForecast(data.forecast);
      setDecision(data.decision);
      setScenario("baseline");
      setStreamCount(data.observations);
      setRsiCandidate(null);
      setMessage("Replay complete · recommendation awaiting human review");
      await refreshSystem();
    } catch (value) {
      setError(value.message);
    } finally {
      setLoading(false);
    }
  }

  async function startStream() {
    setLoading(true);
    setError("");
    setStreamCount(0);
    await api("/api/v1/demo/reset", { method: "POST" });
    const events = new EventSource(`${API}/api/v1/demo/stream?delay_ms=350`);
    events.addEventListener("observation", () => {
      setStreamCount((value) => value + 1);
      setMessage("Streaming observation received · world state updated");
    });
    events.addEventListener("complete", async (event) => {
      const data = JSON.parse(event.data);
      setResult(data);
      setForecast(data.forecast);
      setDecision(data.decision);
      setScenario("baseline");
      setMessage("Streaming loop complete · decision generated");
      setLoading(false);
      events.close();
      await refreshSystem();
    });
    events.onerror = () => {
      setError("The event stream was interrupted.");
      setLoading(false);
      events.close();
    };
  }

  async function simulate(name) {
    setLoading(true);
    setError("");
    try {
      setScenario(name);
      if (name === "baseline") {
        setForecast(result?.forecast || forecast);
      } else {
        const data = await api("/api/v1/scenarios/simulate", {
          method: "POST",
          body: JSON.stringify(SCENARIOS[name]),
        });
        setForecast(data.scenario);
        setMessage(`${name.replaceAll("_", " ")} scenario compared with frozen baseline`);
      }
      await refreshSystem();
    } catch (value) {
      setError(value.message);
    } finally {
      setLoading(false);
    }
  }

  async function review(approved) {
    if (!decision) return;
    try {
      const updated = await api(`/api/v1/decisions/${decision.decision_run_id}/review`, {
        method: "POST",
        body: JSON.stringify({ approved, reviewer: "Datathon demo commander", note: "Demo review" }),
      });
      setDecision(updated);
      setMessage(approved ? "Recommendation approved for coordination" : "Recommendation rejected");
      await refreshSystem();
    } catch (value) {
      setError(value.message);
    }
  }

  async function evaluateRsi() {
    try {
      const candidate = await api("/api/v1/rsi/evaluate", {
        method: "POST",
        body: JSON.stringify({ event_id: "synthetic-demo-001", burned_cells: ["B1", "B2", "A1"] }),
      });
      setRsiCandidate(candidate);
      setMessage("RSI diagnostic created a shadow-only candidate");
      await refreshSystem();
    } catch (value) {
      setError(value.message);
    }
  }

  useEffect(() => { replay(); }, []);

  const cells = forecast?.cells || [];
  const horizonIndex = forecast
    ? Math.max(0, forecast.cells[0].series.findIndex((item) => item.horizon_minutes === horizon))
    : 0;
  const actionByCell = useMemo(
    () => Object.fromEntries((decision?.actions || []).map((item) => [item.cell_id, item])),
    [decision],
  );

  return (
    <main>
      <header>
        <div>
          <p className="eyebrow">IBM LINUXONE · REAL-TIME AI FOR CRITICAL DECISIONS</p>
          <h1>CityShield</h1>
          <p className="subtitle">Wildfire world model · Detect → Predict → Decide → Respond</p>
        </div>
        <div className="headerActions">
          <button className="secondary" onClick={startStream} disabled={loading}>Stream replay</button>
          <button onClick={replay} disabled={loading}>{loading ? "Running…" : "Instant replay"}</button>
        </div>
      </header>

      <section className="statusbar">
        <span className="live"><i /> {message}</span>
        <span>{streamCount} events</span>
        <span>{forecast?.latency_ms ?? "—"} ms inference</span>
        <span>{forecast?.forecast_run_id || "no run"}</span>
      </section>
      {error && <div className="error">{error}</div>}

      <section className="kpis">
        <Kpi label="Platform readiness" value={readiness?.status || "checking"} detail="Only city-specific inputs remain" />
        <Kpi label="Decision mode" value="Advisory only" detail="Human approval is mandatory" />
        <Kpi label="Model evidence" value={`${forecast?.members || 0} members`} detail="P10 / P50 / P90 ensemble" />
        <Kpi label="Audit integrity" value={readiness?.audit?.valid ? "Chain valid" : "Checking"} detail={`${readiness?.audit?.records || 0} signed records`} />
      </section>

      <section className="toolbar panel">
        <div>
          <label>Forecast horizon</label>
          <div className="segments">
            {[30, 60, 120].map((value) => <button className={horizon === value ? "active" : ""} onClick={() => setHorizon(value)} key={value}>{value} min</button>)}
          </div>
        </div>
        <div>
          <label>Paired what-if</label>
          <div className="segments">
            {Object.keys(SCENARIOS).map((name) => <button className={scenario === name ? "active" : ""} onClick={() => simulate(name)} key={name}>{name.replaceAll("_", " ")}</button>)}
          </div>
        </div>
      </section>

      <section className="layout">
        <article className="panel mapPanel">
          <div className="panelTitle">
            <div><span className="step">DETECT + PREDICT</span><h2>{horizon}-minute wildfire risk</h2></div>
            <div className="legend"><span>Low</span><b /><b /><b /><span>High</span></div>
          </div>
          <div className="grid">
            {cells.map((cell) => {
              const point = cell.series[horizonIndex];
              const risk = point?.p90 || 0;
              const action = actionByCell[cell.cell_id];
              return (
                <div className="cell" key={cell.cell_id} style={{ "--risk": risk }}>
                  <div className="cellTop"><strong>{cell.cell_id}</strong><span>P90 {Math.round(risk * 100)}%</span></div>
                  <div className="cellBottom"><small>Population {cell.static.population}</small><em>P{action?.priority || 1}</em></div>
                </div>
              );
            })}
          </div>
          <p className="fineprint">Synthetic 500 m grid. Risk is an uncalibrated ensemble state proxy, not a precise fire perimeter or official warning.</p>
        </article>

        <article className="panel decisionPanel">
          <span className="step">DECIDE + RESPOND</span>
          <h2>Human decision queue</h2>
          <div className="decisionState">{decision?.status?.replaceAll("_", " ") || "not created"}</div>
          <div className="queue">
            {(decision?.actions || []).filter((item) => item.action !== "monitor").slice(0, 5).map((action) => (
              <div className="action" key={action.cell_id}>
                <b>P{action.priority}</b>
                <div><strong>{action.cell_id} · {action.action.replaceAll("_", " ")}</strong><small>{action.reason}</small></div>
              </div>
            ))}
          </div>
          {decision?.status === "pending_human_review" && <div className="reviewButtons"><button className="reject" onClick={() => review(false)}>Reject</button><button onClick={() => review(true)}>Approve for coordination</button></div>}
          <div className="warning">No public alert, evacuation, closure or dispatch is executed automatically.</div>
        </article>
      </section>

      <section className="lowerGrid">
        <article className="panel">
          <span className="step">CONTROLLED RSI</span>
          <h2>Post-event improvement</h2>
          <p>Completed incidents may produce a diagnostic candidate. It remains in shadow until held-out replay, safety review, human approval, versioning and rollback are recorded.</p>
          <button className="secondary" onClick={evaluateRsi}>Run demo evaluation</button>
          {rsiCandidate && <div className="candidate"><strong>{rsiCandidate.status}</strong><span>Brier {rsiCandidate.evaluation.brier_score}</span><small>{rsiCandidate.proposal.recommended_investigation}</small></div>}
        </article>
        <article className="panel">
          <span className="step">DATA SOURCES</span>
          <h2>Adapter readiness</h2>
          <div className="sourceList">{sources.map((source) => <div key={source.source_id}><i className={source.adapter === "implemented" ? "ok" : "wait"} /><span><strong>{source.source_id}</strong><small>{source.role}</small></span><em>{source.ready ? "ready" : "awaiting city"}</em></div>)}</div>
        </article>
        <article className="panel">
          <span className="step">AUDIT</span>
          <h2>Latest evidence trail</h2>
          <div className="auditList">{audits.slice(0, 6).map((record) => <div key={record.hash}><span>{record.sequence}</span><b>{record.event_type.replaceAll("_", " ")}</b><code>{record.hash.slice(0, 8)}</code></div>)}</div>
          <p className="fineprint">{metrics?.observations_ingested || 0} observations · {metrics?.forecasts_created || 0} forecasts · {metrics?.decisions_created || 0} decisions</p>
        </article>
      </section>
    </main>
  );
}

function Kpi({ label, value, detail }) {
  return <article><small>{label}</small><strong>{value}</strong><span>{detail}</span></article>;
}

createRoot(document.getElementById("root")).render(<App />);
