import type { RunDossier } from "../lib/run-dossier-contract";

/** Fixtures project the same typed metric/setup owner into their fact bank. */
export function withDossierResultFacts(dossier: RunDossier): RunDossier {
  return {
    ...dossier,
    outcome: {
      ...dossier.outcome,
      result_fact_bank: {
        symbols: dossier.tested.symbols,
        benchmark_symbol: dossier.outcome.benchmark_symbol,
        config_snapshot: {
          template: dossier.tested.strategy_family,
          timeframe: dossier.tested.timeframe,
          start_date: dossier.tested.start_date,
          end_date: dossier.tested.end_date,
        },
        metrics: { aggregate: { performance: Object.fromEntries(
          dossier.outcome.metrics.map((metric) => [metric.name, metric.value]),
        ) } },
      },
    },
  };
}
