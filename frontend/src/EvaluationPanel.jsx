function format(value, digits = 3) {
  return value == null ? "—" : Number(value).toFixed(digits);
}

function Metric({ label, value, detail }) {
  return <div className="prEvalMetric"><strong>{value}</strong><span>{label}</span>{detail && <small>{detail}</small>}</div>;
}

function BaselineRow({ label, metrics }) {
  return <tr>
    <td>{label}</td>
    <td>{format(metrics.precision)}</td>
    <td>{format(metrics.recall)}</td>
    <td>{format(metrics.iou)}</td>
    <td>{metrics.arrival_time?.median_abs_error_minutes == null ? "—" : `${metrics.arrival_time.median_abs_error_minutes} min`}</td>
  </tr>;
}

export default function EvaluationPanel({ evaluation }) {
  if (!evaluation) {
    return <section className="prEval panel" aria-label="Prediction evaluation"><p className="prLoading">Loading forward evaluation…</p></section>;
  }
  const buckets = ["short", "medium", "long"].map((key) => evaluation.by_lead[key]).filter(Boolean);
  return <section className="prEval panel" aria-label="Prediction evaluation">
    <div className="prSectionHeader">
      <div><p className="eyebrow">FORWARD EVALUATION · FIRMS DETECTION AGREEMENT</p><h2>Did the forecast see the next observation?</h2></div>
      <span className="prEvidenceBadge">Strict t0 → t1</span>
    </div>
    <p className="prSectionLead">{evaluation.protocol.issue_rule}. {evaluation.protocol.validation_rule}. {evaluation.protocol.nist}</p>
    <div className="prEvalBuckets">
      {buckets.map((bucket) => {
        const current = bucket.current;
        const sufficient = bucket.evidence.status === "sufficient";
        return <article className={`prEvalCard ${sufficient ? "sufficient" : "insufficient"}`} key={bucket.id}>
          <div className="prEvalCardTop">
            <div><strong>{bucket.label}</strong><small>{bucket.window_count} window{bucket.window_count === 1 ? "" : "s"} · {bucket.min_minutes}–{bucket.max_minutes >= 100000 ? "∞" : bucket.max_minutes} min lead</small></div>
            <span className={`prEvidence ${sufficient ? "sufficient" : "insufficient"}`}>{sufficient ? "Reporting floor met" : "Below reporting floor"}</span>
          </div>
          {bucket.window_count === 0 ? <p className="prEvalEmpty">No forecast windows fell in this lead band. No score is shown.</p> : <>
            <div className="prEvalCounts">
              <span><b>{current.counts.observed_cells}</b> observed new cells</span>
              <span><b>{current.counts.predicted_cells}</b> predicted cells</span>
              <span><b>{current.counts.true_positive}</b> matched</span>
            </div>
            {sufficient ? <>
              <div className="prMetricGrid">
                <Metric label="Precision" value={format(current.precision)} detail="predicted cells that were observed" />
                <Metric label="Recall / hit rate" value={format(current.recall)} detail="observed cells that were predicted" />
                <Metric label="IoU" value={format(current.iou)} detail="spatial overlap" />
                <Metric label="Arrival median error" value={current.arrival_time?.median_abs_error_minutes == null ? "—" : `${current.arrival_time.median_abs_error_minutes} min`} detail={`${current.counts.matched_arrival_cells} matched cells`} />
                <Metric label="Population abs error" value={current.population?.absolute_error?.toLocaleString() ?? "—"} detail={`observed ${current.population?.observed_exposed?.toLocaleString() ?? "—"} · predicted ${current.population?.predicted_exposed?.toLocaleString() ?? "—"}`} />
                <Metric label="Miss distance" value={current.nearest_distance?.median_miss_distance_m == null ? "—" : `${current.nearest_distance.median_miss_distance_m} m`} detail={`false-alarm distance ${current.nearest_distance?.median_false_alarm_distance_m ?? "—"} m`} />
              </div>
              <table className="prEvalTable">
                <thead><tr><th>Variant</th><th>Precision</th><th>Recall</th><th>IoU</th><th>Arrival error</th></tr></thead>
                <tbody>
                  <BaselineRow label="Current wind/slope model" metrics={current} />
                  <BaselineRow label="Radial 1.5 km/h baseline" metrics={bucket.baseline_radial} />
                  <BaselineRow label="Persistence baseline" metrics={bucket.baseline_persistence} />
                </tbody>
              </table>
              <p className="prEvalNote">The current model has higher IoU than the radial baseline but lower recall: the radial baseline over-predicts widely and catches more detections. This is a trade-off, not a win.</p>
            </> : <>
              <p className="prEvalInsufficient">Below the configured reporting floor: {bucket.evidence.reasons.join("; ")}. No headline score is shown; the raw metrics are available for transparency only.</p>
              <details className="prRawMetrics"><summary>Raw metrics (not evidence)</summary><div className="prEvalCounts"><span>precision <b>{format(current.precision)}</b></span><span>recall <b>{format(current.recall)}</b></span><span>IoU <b>{format(current.iou)}</b></span><span>arrival <b>{current.arrival_time?.median_abs_error_minutes == null ? "—" : `${current.arrival_time.median_abs_error_minutes} min`}</b></span></div></details>
            </>}
          </>}
        </article>;
      })}
    </div>
    <div className="prEvalProtocol">
      <div><small>POSITIVE DEFINITION</small><span>{evaluation.protocol.positive_definition}</span></div>
      <div><small>THRESHOLD</small><span>{evaluation.protocol.probability_threshold}</span></div>
      <div><small>DATA VERSION</small><span>{evaluation.data_version}</span></div>
      <div><small>MODEL</small><span>{evaluation.model_version}</span></div>
    </div>
    <ul className="prLimits">{evaluation.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
  </section>;
}
