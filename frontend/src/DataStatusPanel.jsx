import { useEffect, useMemo, useState } from "react";

const API = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");

const STATUS_LABEL = {
  pass: "Pass",
  warn: "Limitation",
  blocked: "Blocked",
  info: "Context",
  fail: "Fail",
};

const LAYER_LABEL = {
  firms: "NASA FIRMS",
  nist: "NIST maps",
  population: "ACS population",
  roads: "Census roads",
  terrain: "USGS terrain",
  grid: "Shared grid",
  fuel: "Fuel",
  water: "Water",
  critical_facilities: "Facilities",
  shelters: "Shelters",
  time: "Time zone",
};

function timestamp(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-US", {
    timeZone: "America/Los_Angeles",
    dateStyle: "medium",
    timeStyle: "short",
  }) + " PT";
}

export default function DataStatusPanel({ active = true }) {
  const [report, setReport] = useState(null);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!active) return undefined;
    let current = true;
    Promise.all([
      fetch(`${API}/api/v1/paradise/data-quality`).then((response) => {
        if (!response.ok) throw new Error("Data quality report is unavailable");
        return response.json();
      }),
      fetch(`${API}/api/v1/paradise/grid/summary`).then((response) => {
        if (!response.ok) throw new Error("Shared grid is unavailable");
        return response.json();
      }),
    ])
      .then(([quality, grid]) => {
        if (!current) return;
        setReport(quality);
        setSummary(grid);
        setError("");
      })
      .catch((cause) => {
        if (current) setError(cause.message);
      });
    return () => { current = false; };
  }, [active]);

  const orderedChecks = useMemo(() => {
    if (!report) return [];
    const priority = { blocked: 0, warn: 1, fail: 2, pass: 3, info: 4 };
    return [...report.checks].sort((left, right) =>
      priority[left.status] - priority[right.status] || left.id.localeCompare(right.id)
    );
  }, [report]);

  if (error) {
    return <section className="dataStatus panel" aria-label="Data status"><p className="dataStatusError" role="alert">{error}</p></section>;
  }
  if (!report || !summary) {
    return <section className="dataStatus panel" aria-label="Data status"><p className="dataStatusLoading">Loading frozen data status…</p></section>;
  }

  const counts = report.overall.counts;
  const visible = expanded ? orderedChecks : orderedChecks.slice(0, 6);
  const firms = report.coverage.firms;
  const nist = report.coverage.nist;
  const population = report.coverage.population;

  return <section className="dataStatus panel" aria-label="Camp Fire data status">
    <div className="dataStatusHeader">
      <div>
        <p className="eyebrow">DATA STATUS · CAMP FIRE 2018</p>
        <h2>What is real, what is derived, and what is missing</h2>
        <p>{report.overall.summary}</p>
      </div>
      <span className={`dataBadge ${report.overall.status}`}>{report.overall.status_label}</span>
    </div>

    <div className="dataStatusStats">
      <div><small>SHARED GRID</small><strong>{summary.cell_count} cells</strong><span>{summary.resolution_m} m · {summary.cols}×{summary.rows} · {summary.buffer_m / 1000} km buffer</span><em>ID rule {summary.id_rule.split(";")[0]}</em></div>
      <div><small>NASA FIRMS</small><strong>{firms.record_count.toLocaleString()} detections</strong><span>{firms.unique_acquisition_times} snapshots · {firms.first_acquired_at_local?.slice(0, 16).replace("T", " ")} PT →</span><em>Not a perimeter; {firms.outside_grid_extent} points outside grid</em></div>
      <div><small>ACS POPULATION</small><strong>{Math.round(population.allocated_estimate).toLocaleString()}</strong><span>{population.vintage} · {population.block_groups} block groups</span><em>{population.difference_pct}% below place estimate; no resident locations</em></div>
      <div><small>NIST TIMELINE</small><strong>{nist.windows.length} windows</strong><span>{nist.continuous ? "Continuous 06:25–10:00 PT" : "Discontinuous"}</span><em>{nist.digitized_spatial_records === 0 ? "Spatial symbols not digitized" : `${nist.digitized_spatial_records} spatial records`}</em></div>
    </div>

    <div className="dataStatusCounts" aria-label="Check counts">
      <span className="pass"><b>{counts.pass}</b> passed</span>
      <span className="warn"><b>{counts.warn}</b> limitations</span>
      <span className="blocked"><b>{counts.blocked}</b> blocked</span>
      <span className="info"><b>{counts.info}</b> context</span>
      <span className="dataVersion">data {report.data_version}</span>
    </div>

    <div className="dataCheckList">
      {visible.map((check) => <div className={`dataCheck ${check.status}`} key={check.id}>
        <span className="dataCheckStatus">{STATUS_LABEL[check.status] || check.status}</span>
        <div>
          <strong>{LAYER_LABEL[check.layer] || check.layer} · {check.summary}</strong>
          {check.detail && <small>{check.detail}</small>}
        </div>
      </div>)}
    </div>
    {orderedChecks.length > 6 && <button className="textButton dataExpand" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}>{expanded ? "Show fewer checks" : `Show all ${orderedChecks.length} checks`}</button>}
    <p className="dataStamp">Generated {timestamp(report.generated_at)} · source hashes and every check are in <code>data/paradise/data_quality_report.json</code>. A warning is a declared limitation, not a hidden failure. Missing layers are never filled with invented data.</p>
  </section>;
}
