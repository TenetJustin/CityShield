export const RISK_COLORS = {
  low: "#245f4d",
  watch: "#bda449",
  elevated: "#ee8139",
  high: "#e5422d",
};

export function riskColor(risk) {
  if (risk >= 0.6) return RISK_COLORS.high;
  if (risk >= 0.3) return RISK_COLORS.elevated;
  if (risk >= 0.1) return RISK_COLORS.watch;
  return RISK_COLORS.low;
}
