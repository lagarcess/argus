import type { CommandPaletteAssetRollup } from "@/lib/command-palette-items";

type AssetHistoryRollupProps = {
  rollup: CommandPaletteAssetRollup;
};

export function AssetHistoryRollup({ rollup }: AssetHistoryRollupProps) {
  return (
    <section
      className="rounded-[14px] border border-[#5ba897]/20 bg-[#5ba897]/[0.06] px-4 py-3 dark:border-[#7bc1ad]/20 dark:bg-[#7bc1ad]/[0.06]"
      aria-label={rollup.heading}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-black/40 dark:text-white/40">
            {rollup.heading}
          </p>
          <p className="mt-1 font-display text-[18px] font-semibold text-black dark:text-white">
            {rollup.symbol}
          </p>
          <p className="mt-0.5 text-[11px] text-black/40 dark:text-white/40">
            {rollup.scope}
          </p>
        </div>
        <p className="text-right text-[11px] text-black/35 dark:text-white/35">
          {rollup.lastTouched}
        </p>
      </div>
      <p className="mt-1 text-[13px] text-black/60 dark:text-white/60">
        {rollup.runs}
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {rollup.decisions.map((decision) => (
          <span
            key={decision.state}
            className="rounded-full border border-black/8 bg-white/55 px-2 py-1 text-[10px] font-semibold text-black/50 dark:border-white/10 dark:bg-white/[0.04] dark:text-white/50"
          >
            {decision.label}
          </span>
        ))}
      </div>
    </section>
  );
}
