import { CheckCircle2 } from "lucide-react";
import { StrategyConfirmationPayload } from "./types";
import { splitPeriodDisplay, splitSymbolList } from "./card-formatting";

type StrategyConfirmationCardProps = {
  confirmation: StrategyConfirmationPayload;
};

export default function StrategyConfirmationCard({ confirmation }: StrategyConfirmationCardProps) {
  const primaryRows = confirmation.rows.slice(0, 3);
  const detailRows = confirmation.rows.slice(3);

  return (
    <section className="w-full rounded-[20px] border border-black/12 bg-white dark:border-white/12 dark:bg-[#1d2023] overflow-hidden">
      <div className="flex items-start justify-between gap-3 border-b border-black/8 px-4 py-3.5 dark:border-white/8 sm:px-5">
        <div className="min-w-0">
          <p className="text-[14px] font-medium leading-snug tracking-tight text-black dark:text-white sm:text-[15px]">
            {confirmation.title}
          </p>
          <p className="mt-1 text-[12px] leading-[1.45] text-black/50 dark:text-white/50">
            {confirmation.summary}
          </p>
        </div>
        <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-black/10 bg-black/[0.03] px-2.5 py-1 text-[11px] font-medium tracking-tight text-black/70 dark:border-white/10 dark:bg-white/[0.04] dark:text-white/70">
          <CheckCircle2 className="h-3 w-3" />
          {confirmation.statusLabel}
        </span>
      </div>

      <div className="px-4 py-4 sm:px-5">
        <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {primaryRows.map((row) => (
            <div key={row.label} className="min-w-0">
              <dt className="text-[11px] uppercase tracking-[0.08em] text-black/45 dark:text-white/45">
                {row.label}
              </dt>
              <ConfirmationValue row={row} />
            </div>
          ))}
        </dl>

        {detailRows.length > 0 && (
          <dl className="mt-4 grid grid-cols-1 gap-3 border-t border-black/8 pt-4 dark:border-white/8 sm:grid-cols-2">
            {detailRows.map((row) => (
              <div key={row.label} className="min-w-0">
                <dt className="text-[12px] text-black/45 dark:text-white/45">
                  {row.label}
                </dt>
                <dd className="mt-0.5 whitespace-normal break-words text-[14px] font-medium leading-[1.45] text-black dark:text-white">
                  {row.value}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </div>

      {confirmation.assumptions && confirmation.assumptions.length > 0 && (
        <div className="flex flex-wrap gap-x-3 gap-y-1 border-t border-black/8 px-4 py-3 dark:border-white/8 sm:px-5">
          {confirmation.assumptions.map((text) => (
            <span key={text} className="flex min-w-0 items-start gap-1.5 whitespace-normal break-words text-[11px] leading-snug text-black/45 dark:text-white/45">
              <span className="h-1 w-1 rounded-full bg-black/20 dark:bg-white/20" />
              {text}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}

function ConfirmationValue({
  row,
}: {
  row: StrategyConfirmationPayload["rows"][number];
}) {
  if (row.label.toLowerCase() === "assets") {
    return <AssetList symbols={splitSymbolList(row.value)} />;
  }
  if (row.label.toLowerCase() === "period") {
    const period = splitPeriodDisplay(row.value);
    return (
      <dd className="mt-1 text-[15px] font-semibold leading-snug tracking-tight text-black dark:text-white">
        <span className="block whitespace-normal break-words">{period.label}</span>
        {period.dates && (
          <span className="mt-0.5 block text-[13px] font-medium leading-snug text-black/58 dark:text-white/58">
            {period.dates}
          </span>
        )}
      </dd>
    );
  }
  return (
    <dd className="mt-1 whitespace-normal break-words text-[15px] font-semibold leading-snug tracking-tight text-black dark:text-white">
      {row.value}
    </dd>
  );
}

function AssetList({ symbols }: { symbols: string[] }) {
  if (symbols.length === 0) {
    return (
      <dd className="mt-1 text-[15px] font-semibold leading-snug tracking-tight text-black dark:text-white">
        Selected asset
      </dd>
    );
  }
  return (
    <dd className="mt-1 flex flex-wrap gap-x-2 gap-y-1">
      {symbols.map((symbol) => (
        <span
          key={symbol}
          className="rounded-[5px] border border-[#c2a44d]/25 bg-[#c2a44d]/10 px-1.5 py-0.5 text-[13px] font-semibold leading-none tracking-tight text-[#8b7329] dark:border-[#c2a44d]/30 dark:bg-[#c2a44d]/12 dark:text-[#d9c574]"
        >
          {symbol}
        </span>
      ))}
    </dd>
  );
}
