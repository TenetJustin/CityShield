import { useMemo } from "react";
import { riskColor } from "./riskVisual.js";

const PAD = 320;

function lines(geometry) {
  if (!geometry) return [];
  if (geometry.type === "LineString") return [geometry.coordinates];
  if (geometry.type === "MultiLineString") return geometry.coordinates;
  if (geometry.type === "Polygon") return geometry.coordinates;
  if (geometry.type === "MultiPolygon") return geometry.coordinates.flat();
  return [];
}

function projection(grid) {
  const { origin, meters_per_degree_longitude: mplon, meters_per_degree_latitude: mplat } = grid.crs;
  const extent = grid.extent;
  const xMin = extent.x_min_m;
  const yMax = extent.y_max_m;
  const width = extent.x_max_m - extent.x_min_m + PAD * 2;
  const height = extent.y_max_m - extent.y_min_m + PAD * 2;
  const project = (longitude, latitude) => ({
    x: (longitude - origin.longitude) * mplon - xMin + PAD,
    y: yMax - (latitude - origin.latitude) * mplat + PAD,
  });
  return { project, width, height };
}

function pathForCoordinates(coordinates, project, close = false) {
  return coordinates.map((point, index) => {
    const value = project(point[0], point[1]);
    return `${index ? "L" : "M"}${value.x.toFixed(1)},${value.y.toFixed(1)}`;
  }).join(" ") + (close ? " Z" : "");
}

export default function ParadiseGridMap2D({
  grid,
  geography,
  frame,
  forecast,
  selectedCell,
  onSelect,
  layers,
}) {
  const view = useMemo(() => (grid ? projection(grid) : null), [grid]);
  const roads = useMemo(() => {
    if (!geography || !view) return [];
    return geography.features.slice(1).map((feature, index) => ({
      id: index,
      major: ["S1100", "S1200"].includes(feature.properties?.mtfcc),
      d: lines(feature.geometry).map((line) => pathForCoordinates(line, view.project)).join(" "),
    }));
  }, [geography, view]);
  const boundary = useMemo(() => {
    if (!grid || !view) return "";
    return lines(grid.town.boundary).map((ring) => pathForCoordinates(ring, view.project, true)).join(" ");
  }, [grid, view]);

  if (!grid || !view) {
    return <div className="prMap prMapEmpty">Loading the shared Paradise grid…</div>;
  }
  const observed = new Set(frame?.cumulative_detected_cells || []);
  const predicted = new Map((forecast?.cells || []).map((cell) => [cell.cell_id, cell]));
  const hotspots = (frame?.new_detections || []).filter((item) => item.cell_id);
  const maxPopulation = Math.max(1, ...grid.cells.map((cell) => cell.population));
  const townCenter = view.project(
    (grid.town.bounds_wgs84[0] + grid.town.bounds_wgs84[2]) / 2,
    (grid.town.bounds_wgs84[1] + grid.town.bounds_wgs84[3]) / 2,
  );
  const selected = grid.cells.find((cell) => cell.id === selectedCell);
  const hasPrediction = Boolean(forecast?.cells?.length);

  return <div className="prMap">
    <div className="prMapTop"><span>REAL 500 m PARADISE GRID</span><span>NORTH ↑ · LOCAL METRIC GRID</span></div>
    <svg viewBox={`0 0 ${view.width} ${view.height}`} className="prMapSvg" role="img" aria-label="Paradise Camp Fire replay grid with roads, observed detections and model prediction">
      <rect width={view.width} height={view.height} fill="#081813" />
      <g>
        {grid.cells.map((cell) => {
          const prediction = predicted.get(cell.id);
          const isObserved = observed.has(cell.id);
          const isSelected = cell.id === selectedCell;
          let fill = cell.in_town ? "#14352a" : "#0c2019";
          let opacity = 0.72;
          if (layers.prediction && prediction) {
            if (prediction.probability >= (forecast?.threshold ?? 0.5)) {
              fill = riskColor(prediction.probability);
              opacity = 0.38;
            } else {
              fill = "#31594a";
              opacity = 0.13;
            }
          }
          if (layers.observed && isObserved) {
            fill = "#a95424";
            opacity = 0.6;
          }
          const x = cell.x_m - cell.size_m / 2 - grid.extent.x_min_m + PAD;
          const y = grid.extent.y_max_m - (cell.y_m + cell.size_m / 2) + PAD;
          return <g key={cell.id}>
            <rect
              x={x}
              y={y}
              width={cell.size_m}
              height={cell.size_m}
              fill={fill}
              fillOpacity={opacity}
              stroke={isSelected ? "#f5ffdf" : layers.observed && isObserved ? "#ffb27a" : "#31594a"}
              strokeWidth={isSelected ? 22 : layers.observed && isObserved ? 7 : 2}
              onClick={() => onSelect(cell.id)}
              className="prCell"
            />
            {layers.prediction && prediction && prediction.probability >= (forecast?.threshold ?? 0.5) && !isObserved && <rect
              x={x + 55} y={y + 55} width={cell.size_m - 110} height={cell.size_m - 110}
              fill="none" stroke="#ffe1a3" strokeWidth="7" strokeDasharray="18 12" pointerEvents="none" opacity="0.68"
            />}
            {layers.population && cell.population > 0 && <rect
              x={x + 18}
              y={y + cell.size_m - 34}
              width={(cell.size_m - 36) * (cell.population / maxPopulation)}
              height="16"
              fill="#d7a84b"
              opacity="0.75"
              pointerEvents="none"
            />}
          </g>;
        })}
      </g>
      {layers.roads && <g>
        {roads.map((road) => <path key={road.id} d={road.d} fill="none" stroke={road.major ? "#e4c783" : "#6f9d83"} strokeWidth={road.major ? 26 : 12} opacity={road.major ? 0.9 : 0.58} />)}
      </g>}
      {boundary && <path d={boundary} fill="none" stroke="#bde5a8" strokeWidth="30" opacity="0.95" />}
      {layers.hotspots && hotspots.map((hotspot) => {
        const point = view.project(hotspot.longitude, hotspot.latitude);
        const radius = 28 + Math.min(90, Math.max(0, hotspot.frp || 0) * 2.2);
        return <g key={hotspot.provider_record_id}>
          <circle cx={point.x} cy={point.y} r={radius} fill="#ffd05a" fillOpacity="0.82" stroke="#5c3a20" strokeWidth="6" />
        </g>;
      })}
      <text x={townCenter.x} y={townCenter.y - 220} textAnchor="middle" fill="#e7f3dc" fontSize="190" fontWeight="800" opacity="0.72">PARADISE</text>
      {selected && <circle cx={selected.x_m - grid.extent.x_min_m + PAD} cy={grid.extent.y_max_m - selected.y_m + PAD} r="26" fill="none" stroke="#f5ffdf" strokeWidth="12" pointerEvents="none" />}
    </svg>
    <div className="prMapFoot">
      {frame?.nist_window ? "NIST window active · spatial symbols not digitized" : hasPrediction ? `Predicted at +${forecast.lead_minutes} min · probability threshold ${forecast.threshold}` : "No mapped observation at this frame"}
      {" · "}Observed cells are FIRMS detection proxies; predicted cells are a risk envelope, not a burned perimeter
    </div>
    {frame?.nist_window && !frame?.observation_count && <div className="prNistBadge">NIST time window only<br /><small>No spatial symbols are available</small></div>}
  </div>;
}
