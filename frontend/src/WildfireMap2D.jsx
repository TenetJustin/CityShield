import { useMemo } from "react";
import { riskColor } from "./riskVisual.js";

const SIZE = 90;
const GAP = 8;
const MARGIN = 42;

export default function WildfireMap2D({
  cells,
  selectedCell,
  onSelect,
  showObserved = false,
  showHotspots = false,
  resources = [],
}) {
  const bounds = useMemo(() => {
    if (!cells.length) return { minRow: 0, minCol: 0, rows: 3, cols: 3 };
    const rows = cells.map((cell) => cell.row);
    const cols = cells.map((cell) => cell.col);
    const minRow = Math.min(...rows);
    const minCol = Math.min(...cols);
    return {
      minRow,
      minCol,
      rows: Math.max(...rows) - minRow + 1,
      cols: Math.max(...cols) - minCol + 1,
    };
  }, [cells]);
  const width = bounds.cols * (SIZE + GAP) - GAP + MARGIN * 2;
  const height = bounds.rows * (SIZE + GAP) - GAP + MARGIN * 2;
  const cellPosition = (cell) => ({
    x: MARGIN + (cell.col - bounds.minCol) * (SIZE + GAP),
    y: MARGIN + (cell.row - bounds.minRow) * (SIZE + GAP),
  });

  return (
    <div className="map2dWrap">
      <div className="map2dTop"><span>2D RISK GRID</span><span>SCHEMATIC · NORTH ↑</span></div>
      {cells.length ? (
        <svg className="map2dCanvas" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Interactive two-dimensional wildfire risk grid">
          <rect width={width} height={height} fill="#0b1d18" />
          <g aria-hidden="true" stroke="#496957" strokeWidth="1" opacity="0.35">
            {Array.from({ length: bounds.cols + 1 }, (_, index) => <line key={`v-${index}`} x1={MARGIN - GAP / 2 + index * (SIZE + GAP)} x2={MARGIN - GAP / 2 + index * (SIZE + GAP)} y1="0" y2={height} />)}
            {Array.from({ length: bounds.rows + 1 }, (_, index) => <line key={`h-${index}`} x1="0" x2={width} y1={MARGIN - GAP / 2 + index * (SIZE + GAP)} y2={MARGIN - GAP / 2 + index * (SIZE + GAP)} />)}
          </g>
          {cells.map((cell) => {
            const { x, y } = cellPosition(cell);
            const selected = cell.id === selectedCell;
            return (
              <g
                key={cell.id}
                className="map2dCell"
                role="button"
                tabIndex={0}
                aria-label={`${cell.id}, ${Math.round(cell.risk * 100)} percent model risk${cell.observed ? ", observed exercise perimeter" : ""}`}
                onClick={() => onSelect(cell.id)}
                onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(cell.id); } }}
              >
                <rect x={x} y={y} width={SIZE} height={SIZE} rx="9" fill={riskColor(cell.risk)} fillOpacity="0.88" stroke={selected ? "#f5ffdf" : "#8cb79b"} strokeWidth={selected ? 4 : 1.5} />
                <text x={x + 12} y={y + 29} className="map2dCellId">{cell.id}</text>
                <text x={x + 12} y={y + 68} className="map2dCellRisk">{Math.round(cell.risk * 100)}%</text>
                {showObserved && cell.observed && <rect x={x + 5} y={y + 5} width={SIZE - 10} height={SIZE - 10} rx="6" fill="none" stroke="#fff1cf" strokeWidth="3" strokeDasharray="8 5" pointerEvents="none" />}
                {showHotspots && cell.hotspot && <circle cx={x + SIZE - 14} cy={y + 15} r="8" fill="#ffdf72" stroke="#513315" strokeWidth="2" pointerEvents="none" />}
              </g>
            );
          })}
          {resources.map((resource) => {
            const cell = cells.find((item) => item.id === resource.cell_id);
            if (!cell) return null;
            const { x, y } = cellPosition(cell);
            return <g key={resource.resource_id} aria-label={`${resource.kind} resource in ${cell.id}`} pointerEvents="none">
              <circle cx={x + SIZE - 17} cy={y + SIZE - 17} r="14" fill="#d9f7df" stroke="#173b2b" strokeWidth="2" />
              <text x={x + SIZE - 17} y={y + SIZE - 12} className="map2dResource">{resource.kind === "drone" ? "D" : "+"}</text>
            </g>;
          })}
        </svg>
      ) : <div className="sceneFallback">Start the demo to see the wildfire world state.</div>}
      <div className="map2dFoot">Grid positions are illustrative; no georeferenced road or resident locations are loaded.</div>
    </div>
  );
}
