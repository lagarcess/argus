/** Frozen evidence visual shared by declared cards and existing receipts. */
export type EvidenceVisualPoint = { time: string; value: number };

export type EvidenceVisual = {
  kind: "portfolio_equity";
  currency?: string | null;
  base_value?: number | null;
  series: EvidenceVisualPoint[];
};

export function parseEvidenceVisual(value: unknown): EvidenceVisual | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const visual = value as Record<string, unknown>;
  if (visual.kind !== "portfolio_equity" ||
    (visual.currency != null && typeof visual.currency !== "string") ||
    (visual.base_value != null && (typeof visual.base_value !== "number" || !Number.isFinite(visual.base_value))) ||
    !Array.isArray(visual.series) || !visual.series.every((point) =>
      typeof point === "object" && point !== null && typeof point.time === "string" &&
      point.time.length > 0 && typeof point.value === "number" && Number.isFinite(point.value))) return null;
  return value as EvidenceVisual;
}
