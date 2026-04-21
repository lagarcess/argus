export function normalizeWinRate(winRate?: number | null): number {
  if (winRate === null || winRate === undefined) return 0;
  return winRate > 1 ? winRate / 100 : winRate;
}

export function formatWinRatePercent(winRate?: number | null): string {
  return `${(normalizeWinRate(winRate) * 100).toFixed(1)}%`;
}

export function normalizeFidelityScore(score?: number | null): number {
  if (score === null || score === undefined) return 0;
  return score > 1 ? score / 100 : score;
}
