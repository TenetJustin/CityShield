import { useEffect, useState } from "react";

const API = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");
const HORIZONS = [30, 60, 120];

function localTime(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-US", {
    timeZone: "America/Los_Angeles",
    dateStyle: "medium",
    timeStyle: "short",
  }) + " PT";
}

function statusLabel(status) {
  if (status === "advisory_ready") return "Advisory ready";
  if (status === "abstained_no_observations") return "No mapped observation · abstained";
  if (status === "input_incomplete") return "Required source unavailable";
  return "Checking live inputs";
}

export default function LiveDecisionLoop() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load(force = false) {
    setLoading(true);
    try {
      const response = await fetch(`${API}/api/v1/paradise/nowcast?refresh=${force}`);
      if (!response.ok) throw new Error(`Live decision service returned HTTP ${response.status}`);
      setData(await response.json());
      setError("");
    } catch (cause) {
      setError(cause.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(false);
    const timer = window.setInterval(() => load(false), 300000);
    return () => window.clearInterval(timer);
  }, []);

  const sourceOk = (id) => data?.sources?.[id]?.status === "ok";
  return <section className="liveLoop panel" id="live-decision-loop" aria-label="Live AI decision loop">
    <div className="liveLoopHeader">
      <div>
        <p className="eyebrow">REAL-TIME AI · CRITICAL DECISION LOOP</p>
        <h2>From new observations to a human decision queue</h2>
        <p>Current NASA and NOAA data enter the same Paradise grid used by the evaluated replay. CityShield predicts 30/60/120-minute risk, ranks exposed areas and stops when required evidence is missing.</p>
      </div>
      <button className="primaryButton" onClick={() => load(true)} disabled={loading}>{loading ? "Updating…" : "Run live update"}</button>
    </div>

    {error && <p className="liveLoopError" role="alert">{error}. The last completed result remains visible.</p>}
    <div className="livePipeline" aria-label="Live inference pipeline">
      {(data?.telemetry?.pipeline || ["FIRMS + NOAA", "Paradise 500 m grid", "24-member ensemble", "30/60/120 min risk", "human review queue"]).map((step, index) => <div key={step}><b>{index + 1}</b><span>{step}</span>{index < 4 && <i>→</i>}</div>)}
    </div>

    <div className="liveLoopGrid">
      <article className="liveStatusCard">
        <div className="liveCardTop"><p className="eyebrow">LIVE INPUTS</p><span className={`liveState ${data?.status || "loading"}`}>{statusLabel(data?.status)}</span></div>
        <strong className="liveBig">{data ? `${data.observation.detections} detections` : "Checking…"}</strong>
        <p>{data?.status_message || "Reading the latest source snapshot."}</p>
        <dl className="liveFacts">
          <div><dt>FIRMS</dt><dd className={sourceOk("nasa-firms") ? "ok" : "warn"}>{data?.sources?.["nasa-firms"]?.status || "checking"}</dd></div>
          <div><dt>NOAA weather</dt><dd className={sourceOk("noaa-nws") ? "ok" : "warn"}>{data?.sources?.["noaa-nws"]?.status || "checking"}</dd></div>
          <div><dt>Mapped seed cells</dt><dd>{data?.observation?.mapped_seed_cells?.length ?? "—"}</dd></div>
          <div><dt>Latest detection</dt><dd>{localTime(data?.observation?.latest_detection_at)}</dd></div>
          <div><dt>Weather input</dt><dd>{data?.weather ? `${data.weather.wind_speed_m_s} m/s · ${data.weather.humidity_pct}% RH` : "not available"}</dd></div>
        </dl>
        <small className="liveCaution">Zero detections does not prove safety. FIRMS points are not a fire perimeter.</small>
      </article>

      <article className="liveForecastCard">
        <p className="eyebrow">AI RISK OUTLOOK</p>
        <div className="liveHorizons">
          {HORIZONS.map((minutes) => {
            const forecast = data?.forecasts?.[String(minutes)];
            return <div key={minutes} className={forecast ? "ready" : "empty"}>
              <small>+{minutes} MIN</small>
              <strong>{forecast ? forecast.summary.predicted_new_cells : "—"}</strong>
              <span>{forecast ? "new risk cells" : "no forecast issued"}</span>
              <em>{forecast ? `${Math.round(forecast.summary.predicted_new_population).toLocaleString()} people mapped` : "model abstained"}</em>
            </div>;
          })}
        </div>
        <div className="liveConfidence"><span>Confidence</span><b>{data?.confidence?.label || "—"}</b><p>{data?.confidence?.reason || "Waiting for a completed run."}</p></div>
      </article>

      <article className="liveActionsCard">
        <div className="liveCardTop"><p className="eyebrow">RECOMMENDED NEXT ACTION</p><span className="liveReview">Human review required</span></div>
        <div className="liveActions">
          {(data?.actions || []).map((item) => <div key={`${item.priority}-${item.action}`}><b>P{item.priority}</b><span><strong>{item.action}</strong><small>{item.reason}</small>{item.target_cells.length > 0 && <code>{item.target_cells.join(" · ")}</code>}</span></div>)}
          {!data && <p>Decision queue appears after the first source check.</p>}
        </div>
        <small className="liveCaution">{data?.safety || "Recommendations never trigger public alerts or dispatch automatically."}</small>
      </article>

      <article className="liveEvidenceCard">
        <p className="eyebrow">LINUXONE RUN EVIDENCE</p>
        <dl className="liveFacts">
          <div><dt>Target</dt><dd>{data?.telemetry?.deployment_target || "IBM LinuxONE"}</dd></div>
          <div><dt>Architecture</dt><dd>{data?.telemetry?.runtime_architecture || "—"}</dd></div>
          <div><dt>Git commit</dt><dd><code>{data?.telemetry?.git_commit || "—"}</code></dd></div>
          <div><dt>Model</dt><dd><code>{data?.telemetry?.model_version || "—"}</code></dd></div>
          <div><dt>Inference</dt><dd>{data ? `${data.telemetry.inference_latency_ms} ms` : "—"}</dd></div>
          <div><dt>Snapshot</dt><dd>{localTime(data?.telemetry?.source_snapshot_at)}</dd></div>
          <div><dt>Run ID</dt><dd><code>{data?.run_id || "—"}</code></dd></div>
          <div><dt>Audit</dt><dd><code>{data?.audit_hash?.slice(0, 12) || "—"}</code></dd></div>
        </dl>
      </article>
    </div>
  </section>;
}
