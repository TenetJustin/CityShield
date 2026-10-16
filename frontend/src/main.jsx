import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

function App() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  async function replay() {
    setLoading(true);
    await fetch(`${API}/api/v1/demo/reset`, { method: "POST" });
    const response = await fetch(`${API}/api/v1/demo/replay`, { method: "POST" });
    setResult(await response.json());
    setLoading(false);
  }

  useEffect(() => { replay(); }, []);

  const cells = result?.forecast?.cells || [];
  const actions = result?.decision?.actions || [];

  return (
    <main>
      <header>
        <div>
          <p className="eyebrow">IBM LinuxONE · REAL-TIME CRITICAL DECISIONS</p>
          <h1>CityShield</h1>
          <p>Detect → Predict → Decide → Respond</p>
        </div>
        <button onClick={replay} disabled={loading}>{loading ? "Replaying…" : "Replay event"}</button>
      </header>

      <section className="status">
        <span>MODE · SYNTHETIC DEMO</span>
        <span>EXECUTION · ADVISORY ONLY</span>
        <span>HORIZONS · 30 / 60 / 120 MIN</span>
      </section>

      <section className="layout">
        <article className="panel">
          <h2>120-minute fire probability</h2>
          <div className="grid">
            {cells.map((cell) => {
              const risk = cell.series.at(-1).p90;
              return (
                <div className="cell" key={cell.cell_id} style={{ "--risk": risk }}>
                  <strong>{cell.cell_id}</strong>
                  <span>P90 {Math.round(risk * 100)}%</span>
                  <small>Pop. {cell.static.population}</small>
                </div>
              );
            })}
          </div>
          <p className="fineprint">500 m demonstration grid. Probabilities are uncalibrated ensemble proxies.</p>
        </article>

        <article className="panel">
          <h2>Human decision queue</h2>
          <div className="queue">
            {actions.slice(0, 6).map((action) => (
              <div className="action" key={action.cell_id}>
                <b>P{action.priority} · {action.cell_id}</b>
                <span>{action.action.replaceAll("_", " ")}</span>
                <small>{action.reason}</small>
              </div>
            ))}
          </div>
          <div className="warning">No evacuation or dispatch is executed automatically.</div>
        </article>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);

