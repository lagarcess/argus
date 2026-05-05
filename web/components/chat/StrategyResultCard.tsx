import { StrategyResultPayload } from "./types";
import { useTranslation } from "react-i18next";
import { splitPeriodDisplay } from "./card-formatting";

type StrategyResultCardProps = {
  result: StrategyResultPayload;
};

export default function StrategyResultCard({ result }: StrategyResultCardProps) {
  const { t } = useTranslation();
  const period = splitPeriodDisplay(result.period);
  const symbols = result.symbols ?? [];
  return (
    <section className="w-full rounded-[20px] border border-black/12 dark:border-white/12 bg-white dark:bg-[#1d2023] overflow-hidden">
      <div className="flex items-center justify-between gap-3 px-4 sm:px-5 py-3.5 border-b border-black/8 dark:border-white/8">
        <div className="min-w-0">
          {symbols.length > 0 ? (
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <AssetSymbols symbols={symbols} />
              <span className="text-[14px] font-medium leading-snug tracking-tight text-black dark:text-white sm:text-[15px]">
                {result.strategyLabel ?? result.strategyName}
              </span>
            </div>
          ) : (
            <p className="text-[14px] sm:text-[15px] font-medium leading-snug tracking-tight text-black dark:text-white">
              {result.strategyName}
            </p>
          )}
          <p className="mt-1 text-[12px] leading-snug text-black/45 dark:text-white/45">
            <span className="block">{period.label}</span>
            {period.dates && <span className="block">{period.dates}</span>}
          </p>
        </div>
        <span className="shrink-0 rounded-full border border-black/10 dark:border-white/10 bg-black/[0.03] dark:bg-white/[0.04] px-2.5 py-1 text-[11px] font-medium tracking-tight text-black/70 dark:text-white/70">
          {result.statusLabel || t('chat.simulation_complete')}
        </span>
      </div>

      <div className="px-4 sm:px-5 py-5">
        {result.metrics.length > 0 && (
          <div className="mb-6">
            <dt className="text-[12px] uppercase tracking-wider text-black/45 dark:text-white/45 font-semibold">
              {result.metrics[0].label}
            </dt>
            <dd className="text-[32px] sm:text-[40px] font-bold tracking-tight text-black dark:text-white leading-tight">
              {result.metrics[0].value}
            </dd>
          </div>
        )}

        <dl className="grid grid-cols-2 gap-4">
          {result.metrics.slice(1).map((metric) => (
            <div key={metric.label} className="flex flex-col gap-0.5">
              <dt className="text-[12px] leading-snug text-black/45 dark:text-white/45">{metric.label}</dt>
              <dd className="whitespace-normal break-words text-[15px] font-semibold leading-snug tracking-tight text-black dark:text-white">
                {metric.value}
              </dd>
            </div>
          ))}
        </dl>
      </div>

      {(result.benchmarkNote || (result.assumptions && result.assumptions.length > 0)) && (
        <div className="px-4 sm:px-5 py-3 border-t border-black/8 dark:border-white/8 flex flex-col gap-1.5">
          {result.benchmarkNote && (
            <p className="text-[12px] leading-[1.45] text-black/55 dark:text-white/55 italic">
              {result.benchmarkNote}
            </p>
          )}
          {result.assumptions && result.assumptions.length > 0 && (
            <div className="flex flex-wrap gap-x-3 gap-y-1">
              {result.assumptions.map((text, idx) => (
                <span key={idx} className="flex min-w-0 items-start gap-1.5 whitespace-normal break-words text-[11px] leading-snug text-black/45 dark:text-white/45">
                  <span className="w-1 h-1 rounded-full bg-black/20 dark:bg-white/20" />
                  {text}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function AssetSymbols({ symbols }: { symbols: string[] }) {
  return (
    <span className="flex flex-wrap gap-x-1.5 gap-y-1">
      {symbols.map((symbol) => (
        <span
          key={symbol}
          className="rounded-[5px] border border-[#c2a44d]/25 bg-[#c2a44d]/10 px-1.5 py-0.5 text-[12px] font-semibold leading-none tracking-tight text-[#8b7329] dark:border-[#c2a44d]/30 dark:bg-[#c2a44d]/12 dark:text-[#d9c574]"
        >
          {symbol}
        </span>
      ))}
    </span>
  );
}
