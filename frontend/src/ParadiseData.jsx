import { Suspense, lazy, useEffect, useMemo, useState } from "react";

const ParadiseTerrain3D = lazy(() => import("./ParadiseTerrain3D.jsx"));

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const W = 800;
const H = 680;
const PAD = 32;

function lines(geometry) {
  if (!geometry) return [];
  if (geometry.type === "LineString") return [geometry.coordinates];
  if (geometry.type === "MultiLineString") return geometry.coordinates;
  if (geometry.type === "Polygon") return geometry.coordinates;
  if (geometry.type === "MultiPolygon") return geometry.coordinates.flat();
  return [];
}

function timestamp(value) {
  return value ? new Date(value).toLocaleString("en-US", { timeZone: "America/Los_Angeles", dateStyle: "medium", timeStyle: "short" }) + " PT" : "—";
}

export default function ParadiseData() {
  const [geo, setGeo] = useState(null);
  const [historical, setHistorical] = useState(null);
  const [showHistorical, setShowHistorical] = useState(false);
  const [terrain, setTerrain] = useState(null);
  const [mapMode, setMapMode] = useState("2d");
  const [live, setLive] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const responses = await Promise.all([
        fetch(`${API}/api/v1/paradise/geography`),
        fetch(`${API}/api/v1/paradise/live?refresh=true`),
      ]);
      if (responses.some((response) => !response.ok)) throw new Error("Paradise data service is unavailable");
      const [geography, observations] = await Promise.all(responses.map((response) => response.json()));
      setGeo(geography);
      setLive(observations);
      setError("");
    } catch (cause) { setError(cause.message); }
    finally { setLoading(false); }
  }

  useEffect(() => {
    refresh();
    fetch(`${API}/api/v1/paradise/history/camp-fire-final`).then((response) => response.ok ? response.json() : null).then(setHistorical).catch(() => setHistorical(null));
    fetch(`${API}/api/v1/paradise/terrain`).then((response) => response.ok ? response.json() : null).then(setTerrain).catch(() => setTerrain(null));
    const timer = window.setInterval(refresh, 300000);
    return () => window.clearInterval(timer);
  }, []);

  const projection = useMemo(() => {
    if (!geo?.bbox) return null;
    const [west, south, east, north] = geo.bbox;
    const aspect = Math.cos((south + north) * Math.PI / 360);
    const dx = (east - west) * aspect;
    const dy = north - south;
    const scale = Math.min((W - 2 * PAD) / dx, (H - 2 * PAD) / dy);
    const x0 = (W - dx * scale) / 2;
    const y0 = (H - dy * scale) / 2;
    return ([lon, lat]) => [x0 + (lon - west) * aspect * scale, y0 + (north - lat) * scale];
  }, [geo]);

  const path = (coordinates, close = false) => coordinates.map((point, index) => {
    const [x, y] = projection(point);
    return `${index ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ") + (close ? "Z" : "");
  const boundary = geo?.features?.[0];
  const roads = geo?.features?.slice(1) || [];
  const weather = live?.hourly_forecast?.[0];
  const sources = live?.sources || {};

  return <section className="paradisePanel panel" aria-label="Paradise public data">
    <div className="paradiseHeader"><div><p className="eyebrow">PARADISE, CALIFORNIA · PUBLIC DATA</p><h2>Real map and current source observations</h2><p>Town boundary and roads are Census 2025 geography. The 3D view uses USGS 3DEP elevation samples. Weather is a NOAA forecast; incident records come from NIFC. This panel is separate from the exercise forecast below.</p></div><div className="paradiseButtons"><button className="secondaryButton" onClick={() => { setMapMode("2d"); setShowHistorical((value) => !value); }} disabled={!historical} aria-pressed={showHistorical}>{showHistorical ? "Hide 2018 boundary" : "Show 2018 boundary"}</button><button className="secondaryButton" onClick={refresh} disabled={loading}>{loading ? "Checking…" : "Refresh sources"}</button></div></div>
    {error && <p className="paradiseError" role="alert">{error}. Last successful snapshot, if any, remains visible below.</p>}
    <div className="paradiseViewSwitch" role="group" aria-label="Paradise map view"><button className={mapMode === "2d" ? "active" : ""} onClick={() => setMapMode("2d")} aria-pressed={mapMode === "2d"}>2D town map</button><button className={mapMode === "3d" ? "active" : ""} onClick={() => setMapMode("3d")} aria-pressed={mapMode === "3d"} disabled={!terrain}>3D terrain</button><span>{mapMode === "3d" ? "49 USGS samples · vertical relief exaggerated for viewing" : "Census roads · town boundary"}</span></div>
    <div className="paradiseContent">
      {mapMode === "3d" && terrain ? <Suspense fallback={<div className="paradiseMap">Loading 3D terrain…</div>}><ParadiseTerrain3D geography={geo} terrain={terrain} live={live} /></Suspense> : <div className="paradiseMap">
        {projection && <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Paradise town boundary and 2025 Census roads">
          <rect width={W} height={H} fill="#0a1e19" />
          {lines(boundary.geometry).map((ring, index) => <path key={`b-${index}`} d={path(ring, true)} fill="#1b3d30" stroke="#bde5a8" strokeWidth="2.5" />)}
          {showHistorical && historical && lines(historical.geometry).map((ring, index) => <path key={`historic-${index}`} d={path(ring, true)} fill="#d37639" fillOpacity="0.26" stroke="#f09b5e" strokeWidth="2" />)}
          {roads.flatMap((road, index) => lines(road.geometry).map((line, sub) => <path key={`r-${index}-${sub}`} d={path(line)} fill="none" stroke={road.properties.mtfcc === "S1100" || road.properties.mtfcc === "S1200" ? "#e4c783" : "#6f9d83"} strokeWidth={road.properties.mtfcc === "S1100" || road.properties.mtfcc === "S1200" ? "1.8" : "0.8"} opacity="0.8" />))}
          {(live?.incidents || []).map((incident, index) => incident.geometry?.type === "Point" ? <circle key={`i-${index}`} cx={projection(incident.geometry.coordinates)[0]} cy={projection(incident.geometry.coordinates)[1]} r="7" fill="#fb7b4a" stroke="white" strokeWidth="2" /> : null)}
          {(live?.satellite_detections || []).map((detection, index) => <circle key={`h-${index}`} cx={projection([detection.longitude, detection.latitude])[0]} cy={projection([detection.longitude, detection.latitude])[1]} r="4" fill="#f7d367" stroke="#5c3a20" strokeWidth="1" />)}
          <text x="45" y="80" fill="#e7f3dc" fontSize="24" fontWeight="700">PARADISE</text><text x="45" y="103" fill="#abcdb6" fontSize="13">Town boundary · north ↑</text>
          {showHistorical && <text x="45" y="124" fill="#ffc89c" fontSize="12">2018 final perimeter · historical only</text>}
        </svg>}
        {!projection && <span>Loading Census geography…</span>}
      </div>}
      <div className="paradiseFacts">
        <div><small>NOAA HOURLY FORECAST</small><strong>{sources["noaa-nws"]?.status === "ok" ? `${weather?.temperature ?? "—"}°${weather?.temperature_unit || "F"}` : "Unavailable"}</strong><span>{weather ? `${weather.wind_speed_m_s ?? "—"} m/s wind · ${weather.humidity_pct ?? "—"}% humidity` : sources["noaa-nws"]?.error || "Waiting for source"}</span><em>Valid {timestamp(weather?.valid_at)} · issued {timestamp(weather?.forecast_issued_at)}</em></div>
        <div><small>NIFC INCIDENT QUERY</small><strong>{sources["nifc-wfigs"]?.status === "ok" ? `${live.incidents.length} records` : "Unavailable"}</strong><span>{sources["nifc-wfigs"]?.status === "ok" ? "Within the Paradise query area; zero records does not mean no fire." : sources["nifc-wfigs"]?.error || "Waiting for source"}</span></div>
        <div><small>NASA FIRMS DETECTIONS</small><strong>{sources["nasa-firms"]?.status === "ok" ? `${live.satellite_detections.length} detections` : sources["nasa-firms"]?.status === "not_configured" ? "Key needed" : "Unavailable"}</strong><span>{sources["nasa-firms"]?.reason || sources["nasa-firms"]?.error || "Satellite points are not a perimeter."}</span></div>
        <p className="paradiseStamp">Source check: {timestamp(live?.fetched_at)} · Public feeds can be delayed. No official alert, route, dispatch or validated fire prediction is issued here.</p>
        {showHistorical && <p className="paradiseStamp">CAL FIRE 2018 Camp Fire final perimeter, clipped to the town for display. This is an outcome boundary, not a progression timeline; areas inside it were not necessarily burned.</p>}
        <p className="paradiseLinks"><a href="https://www.census.gov/geographies/mapping-files/2025/geo/tiger-line-file.html" target="_blank" rel="noreferrer">Census geography ↗</a><a href="https://www.weather.gov/documentation/services-web-api" target="_blank" rel="noreferrer">NOAA API ↗</a><a href="https://data-nifc.opendata.arcgis.com/" target="_blank" rel="noreferrer">NIFC data ↗</a></p>
      </div>
    </div>
  </section>;
}
