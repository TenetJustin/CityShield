import { useEffect, useMemo, useState } from "react";
import FireShieldMark from "./brand/FireShieldMark.jsx";

const API = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");
const PAD = 300;

function lines(geometry) {
  if (!geometry) return [];
  if (geometry.type === "LineString") return [geometry.coordinates];
  if (geometry.type === "MultiLineString") return geometry.coordinates;
  if (geometry.type === "Polygon") return geometry.coordinates;
  if (geometry.type === "MultiPolygon") return geometry.coordinates.flat();
  return [];
}

function statusCopy(status) {
  if (!status) return {
    signal: "CONNECTING LIVE SOURCES",
    headline: "Building the current picture.",
    detail: "CityShield is aligning fire and weather observations before making a recommendation.",
    tone: "warning",
  };
  if (status === "advisory_ready") return {
    signal: "ESCALATION SIGNAL",
    headline: "Review the live action queue.",
    detail: "Mapped fire observations produced a 30/60/120-minute risk outlook. Human review is required.",
    tone: "alert",
  };
  if (status === "input_incomplete") return {
    signal: "LIVE PICTURE INCOMPLETE",
    headline: "Restore the missing source.",
    detail: "CityShield paused prediction because a required live input is unavailable.",
    tone: "warning",
  };
  return {
    signal: "ROUTINE MONITORING",
    headline: "No mapped fire signal.",
    detail: "Current inputs do not support escalation. Continue monitoring; zero satellite detections do not prove zero risk.",
    tone: "clear",
  };
}

function timeLabel(value) {
  if (!value) return "checking";
  return new Date(value).toLocaleTimeString("en-US", {
    timeZone: "America/Los_Angeles",
    hour: "numeric",
    minute: "2-digit",
  }) + " PT";
}

export default function LandingHero() {
  const [grid, setGrid] = useState(null);
  const [geography, setGeography] = useState(null);
  const [replay, setReplay] = useState(null);
  const [nowcast, setNowcast] = useState(null);
  const [historicalPreview, setHistoricalPreview] = useState(false);
  const [frameIndex, setFrameIndex] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetch(`${API}/api/v1/paradise/grid`, { signal: controller.signal }),
      fetch(`${API}/api/v1/paradise/geography`, { signal: controller.signal }),
      fetch(`${API}/api/v1/paradise/replay`, { signal: controller.signal }),
      fetch(`${API}/api/v1/paradise/nowcast`, { signal: controller.signal }),
    ]).then(async (responses) => {
      if (responses.some((response) => !response.ok)) throw new Error("Landing data unavailable");
      return Promise.all(responses.map((response) => response.json()));
    }).then(([gridData, geographyData, replayData, nowcastData]) => {
      setGrid(gridData);
      setGeography(geographyData);
      setReplay(replayData);
      setNowcast(nowcastData);
      const firstObserved = replayData.frames.findIndex((frame) => frame.observation_count > 0);
      setFrameIndex(firstObserved >= 0 ? firstObserved : 0);
    }).catch(() => {}).finally(() => {});
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!historicalPreview || !replay?.frames?.length) return undefined;
    const timer = window.setInterval(() => {
      setFrameIndex((current) => {
        const next = current + 1;
        return next >= replay.frames.length ? replay.frames.findIndex((frame) => frame.observation_count > 0) : next;
      });
    }, 1100);
    return () => window.clearInterval(timer);
  }, [historicalPreview, replay]);

  const map = useMemo(() => {
    if (!grid) return null;
    const { origin, meters_per_degree_longitude: mplon, meters_per_degree_latitude: mplat } = grid.crs;
    const width = grid.extent.x_max_m - grid.extent.x_min_m + PAD * 2;
    const height = grid.extent.y_max_m - grid.extent.y_min_m + PAD * 2;
    const project = (longitude, latitude) => ({
      x: (longitude - origin.longitude) * mplon - grid.extent.x_min_m + PAD,
      y: grid.extent.y_max_m - (latitude - origin.latitude) * mplat + PAD,
    });
    const path = (coordinates, close = false) => coordinates.map((point, index) => {
      const value = project(point[0], point[1]);
      return `${index ? "L" : "M"}${value.x.toFixed(1)},${value.y.toFixed(1)}`;
    }).join(" ") + (close ? " Z" : "");
    return { width, height, project, path };
  }, [grid]);

  const frame = replay?.frames?.[frameIndex];
  const liveSeeds = new Set(nowcast?.observation?.mapped_seed_cells || []);
  const livePrediction = new Map((nowcast?.forecasts?.["60"]?.cells || []).map((cell) => [cell.cell_id, cell]));
  const historicalCells = new Set(historicalPreview ? frame?.cumulative_detected_cells || [] : []);
  const copy = statusCopy(nowcast?.status);
  const roads = geography?.features?.slice(1) || [];
  const boundary = geography?.features?.[0];

  function getStarted() {
    window.location.assign("/workspace");
  }

  return <section className="landingHero" aria-label="CityShield live decision landing page">
    <div className="landingGlow" />
    <div className="landingCopy">
      <div className="landingBrand"><div className="landingShield"><FireShieldMark /></div><div><strong>CityShield</strong><small>REAL-TIME WILDFIRE DECISION INTELLIGENCE</small></div></div>
      <div className={`landingDecision ${copy.tone}`}><i /><span>{copy.signal}</span><em>LIVE</em></div>
      <p className="landingKicker">REAL-TIME AI FOR CRITICAL DECISIONS</p>
      <h1>See what is changing.<br /><span>Decide what happens next.</span></h1>
      <p className="landingLead">{copy.headline} {copy.detail}</p>
      <div className="landingActions"><button className="landingPrimary" onClick={getStarted}>Open workspace <span>↗</span></button><button className={historicalPreview ? "landingSecondary active" : "landingSecondary"} onClick={() => setHistoricalPreview((value) => !value)}>{historicalPreview ? "Return to live map" : "Preview 2018 spread"}</button></div>
      <a className="landingDocLink" href="/guide">Read the product guide <span>↗</span></a>
      <div className="landingSourceRow"><span><i className={nowcast?.sources?.["nasa-firms"]?.status === "ok" ? "ok" : "warn"} />NASA FIRMS</span><span><i className={nowcast?.sources?.["noaa-nws"]?.status === "ok" ? "ok" : "warn"} />NOAA WEATHER</span><span>UPDATED {timeLabel(nowcast?.telemetry?.source_snapshot_at)}</span></div>
    </div>

    <div className="landingMap" aria-label={historicalPreview ? "Animated 2018 Camp Fire historical preview" : "Current Paradise live decision map"}>
      <div className="landingMapWash" />
      {grid && map && <svg viewBox={`0 0 ${map.width} ${map.height}`} role="img">
        <defs>
          <radialGradient id="landingFire" cx="50%" cy="50%" r="50%"><stop offset="0%" stopColor="#fff0a4" /><stop offset="38%" stopColor="#ef7b32" /><stop offset="100%" stopColor="#9f301c" stopOpacity="0" /></radialGradient>
          <linearGradient id="landingTerrain" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#163b2b" /><stop offset="1" stopColor="#081c15" /></linearGradient>
        </defs>
        <rect width={map.width} height={map.height} fill="url(#landingTerrain)" />
        {lines(boundary?.geometry).map((ring, index) => <path key={`boundary-fill-${index}`} d={map.path(ring, true)} fill="#244c38" fillOpacity=".55" stroke="none" />)}
        <g className="landingRoads">{roads.flatMap((road, index) => lines(road.geometry).map((line, sub) => <path key={`${index}-${sub}`} d={map.path(line)} fill="none" stroke={["S1100", "S1200"].includes(road.properties?.mtfcc) ? "#bfca9e" : "#527c65"} strokeWidth={["S1100", "S1200"].includes(road.properties?.mtfcc) ? 24 : 9} opacity={["S1100", "S1200"].includes(road.properties?.mtfcc) ? .58 : .32} />))}</g>
        <g>{grid.cells.map((cell, index) => {
          const historical = historicalCells.has(cell.id);
          const seed = !historicalPreview && liveSeeds.has(cell.id);
          const prediction = !historicalPreview ? livePrediction.get(cell.id) : null;
          const active = historical || seed || (prediction?.probability >= .5);
          if (!active) return null;
          const x = cell.x_m - grid.extent.x_min_m + PAD;
          const y = grid.extent.y_max_m - cell.y_m + PAD;
          const radius = historical || seed ? 430 : 300 + prediction.probability * 240;
          return <circle key={cell.id} className="landingFireCell" cx={x} cy={y} r={radius} fill="url(#landingFire)" opacity={historical || seed ? .78 : .48} style={{ animationDelay: `${(index % 12) * 70}ms` }} />;
        })}</g>
        {lines(boundary?.geometry).map((ring, index) => <path key={`boundary-${index}`} d={map.path(ring, true)} fill="none" stroke="#b9d9b8" strokeWidth="30" opacity=".72" />)}
        <text x={map.width * .54} y={map.height * .48} textAnchor="middle" fill="#e3f0e5" fontSize="210" fontWeight="800" opacity=".82">PARADISE</text>
        {!historicalPreview && !liveSeeds.size && <g className="landingScan"><circle cx={map.width * .54} cy={map.height * .48} r="650" fill="none" stroke="#84cea2" strokeWidth="18" opacity=".42" /><circle cx={map.width * .54} cy={map.height * .48} r="1150" fill="none" stroke="#84cea2" strokeWidth="10" opacity=".22" /><line x1={map.width * .54} y1={map.height * .48} x2={map.width * .83} y2={map.height * .15} stroke="#b6e7c5" strokeWidth="16" opacity=".34" /></g>}
      </svg>}
      <div className="landingMapTop"><span>{historicalPreview ? "HISTORICAL REPLAY · CAMP FIRE 2018" : "LIVE DECISION VIEW · PARADISE CA"}</span><span>{historicalPreview ? frame?.at_label : "NORTH ↑"}</span></div>
      <div className="landingMapStatus"><span className={historicalPreview ? "historical" : copy.tone}>{historicalPreview ? `${frame?.cumulative_detected_cells?.length || 0} observed cells` : copy.signal}</span><small>{historicalPreview ? "Observed FIRMS progression · historical, not current" : `${liveSeeds.size} mapped fire cells · ${nowcast?.forecasts?.["60"]?.summary?.predicted_new_cells || 0} predicted at +60 min`}</small></div>
      <div className="landingMapLegend"><span><i className="fire" />Observed / predicted fire signal</span><span><i className="town" />Paradise boundary</span><span><i className="road" />Road network</span></div>
    </div>
  </section>;
}
