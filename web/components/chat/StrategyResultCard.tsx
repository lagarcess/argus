import { StrategyResultPayload } from "./types";

type StrategyResultCardProps = {
  result: StrategyResultPayload;
};

export default function StrategyResultCard({ result }: StrategyResultCardProps) {
  return (
    <section className="w-full rounded-[20px] border border-black/12 dark:border-white/12 bg-white dark:bg-[#1d2023] overflow-hidden">
      <div className="flex items-center justify-between gap-3 px-4 sm:px-5 py-3.5 border-b border-black/8 dark:border-white/8">
        <div className="min-w-0">
          <p className="text-[14px] sm:text-[15px] font-medium tracking-tight text-black dark:text-white truncate">
            {result.strategyName}
          </p>
          <p className="text-[12px] text-black/45 dark:text-white/45">{result.period}</p>
        </div>
        <span className="shrink-0 rounded-full border border-black/10 dark:border-white/10 bg-black/[0.03] dark:bg-white/[0.04] px-2.5 py-1 text-[11px] font-medium tracking-tight text-black/70 dark:text-white/70">
          Simulation Complete
        </span>
      </div>

      <div className="px-4 sm:px-5 py-2.5">
        <dl className="divide-y divide-black/8 dark:divide-white/8">
          {result.metrics.map((metric) => (
            <div key={metric.label} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 py-2.5">
              <dt className="text-[13px] sm:text-[14px] text-black/65 dark:text-white/65">{metric.label}</dt>
              <dd className="text-[13px] sm:text-[14px] font-medium tracking-tight text-black dark:text-white text-right">
                {metric.value}
              </dd>
            </div>
          ))}
        </dl>
      </div>

      {result.benchmarkNote ? (
        <div className="px-4 sm:px-5 py-3 border-t border-black/8 dark:border-white/8">
          <p className="text-[12px] leading-[1.45] text-black/55 dark:text-white/55">
            {result.benchmarkNote}
          </p>
        </div>
      ) : null}
    </section>
  );
}
