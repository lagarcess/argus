import type { PublicReceiptPayload } from "@/lib/public-receipt-contract";
import {
  formatReceiptDate,
  interpolate,
  type ReceiptCopy,
} from "@/lib/receipt-copy";
import { benchmarkVerdict, receiptPlan } from "@/lib/receipt-plan";
import type { ArgusLanguage } from "@/lib/language-features";
import ProvenanceMark from "./ProvenanceMark";
import ReceiptChart from "./ReceiptChart";
import ReceiptViewBeacon from "./ReceiptViewBeacon";
import TryArgusCallToAction from "./TryArgusCallToAction";

type ReceiptBodyProps = {
  payload: PublicReceiptPayload;
  createdAt: string | null;
  copy: ReceiptCopy;
  language: ArgusLanguage;
};

/**
 * The shared page. One idea, one outcome, one comparison, at a glance.
 *
 * Built to the house display language rather than as a document: Space Grotesk at
 * display scale with negative tracking, near-black surface, no shadows, one pill
 * action. The earlier version stacked five identically bordered cards of eleven
 * point uppercase labels, which gave the number that matters the same weight as
 * the asset class and read like an itemised bill.
 *
 * Order is deliberate. Someone opening this from a group chat sees the idea, the
 * result, and the comparison first; the not-advice line sits with them rather
 * than in front of them; the exact settings stay complete in the fine print,
 * which is where the design system puts assumptions.
 */
const MUTED = "text-white/45";
const FINE = "text-[12.5px] leading-relaxed";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className={`text-[11px] uppercase tracking-[0.09em] ${MUTED}`}>
        {label}
      </span>
      <span className="font-display text-[15px] tabular-nums text-white/85">
        {value}
      </span>
    </div>
  );
}

export default function ReceiptBody({
  payload,
  createdAt,
  copy,
  language,
}: ReceiptBodyProps) {
  const frozenDate = formatReceiptDate(createdAt, language);
  const frozenLang = payload.content_language;
  const plan = receiptPlan(payload, copy);
  const verdict = benchmarkVerdict(payload, copy);

  const metric = (...keys: string[]) =>
    payload.metrics.find((entry) => keys.includes(entry.key)) ?? null;
  // Metric labels are frozen in English inside the payload. For the keys Argus
  // owns, the label is rendered in the viewer's language instead, the same way
  // the strategy facts are; an unrecognised key keeps its frozen label.
  const metricLabel = (entry: { key: string; label: string }) =>
    (copy.metric_labels as Record<string, string>)[entry.key] ?? entry.label;
  const headline = metric("total_return_pct", "total_return");
  const drawdown = metric("max_drawdown_pct", "max_drawdown");
  const isNegative = Boolean(headline?.value.trim().startsWith("-"));
  const headlineColor = isNegative ? "text-[#d66d75]" : "text-[#5ba897]";

  return (
    <main className="mx-auto flex w-full max-w-[620px] flex-col px-5 pb-16 pt-6 sm:px-8 sm:pt-10">
      <ReceiptViewBeacon />

      <header className="flex items-center justify-between gap-3">
        <span className={`text-[11px] uppercase tracking-[0.1em] ${MUTED}`}>
          {copy.eyebrow}
        </span>
        <ProvenanceMark label={copy.provenance} />
      </header>

      {/* The idea, then what happened to it. Nothing in between. */}
      <h1
        lang={frozenLang}
        className="font-display mt-7 text-[30px] font-medium leading-[1.06] tracking-[-0.9px] text-white sm:text-[40px] sm:tracking-[-1.2px]"
      >
        {payload.idea_title}
      </h1>

      {headline && (
        <div className="mt-8">
          <div
            className={`font-display text-[68px] font-medium leading-[0.92] tracking-[-2.6px] tabular-nums sm:text-[84px] sm:tracking-[-3.2px] ${headlineColor}`}
          >
            {headline.value}
          </div>
          <div className="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            {verdict && (
              <span className="font-display text-[17px] text-white/80 sm:text-[19px]">
                {verdict}
              </span>
            )}
            <span className={`text-[13px] ${MUTED}`}>
              {payload.date_range.display}
            </span>
          </div>
        </div>
      )}

      {/* Above the fold and unmissable, but a line of type rather than a warning
          box arriving before the reader knows what they are looking at. */}
      <section
        aria-label={copy.framing.headline}
        className="mt-8 border-y border-[#c2a44d]/25 py-4"
      >
        <p className="text-[14px] font-medium leading-snug text-[#c2a44d]">
          {copy.framing.headline}
        </p>
        <p className="mt-1.5 text-[13px] leading-relaxed text-white/55">
          {copy.framing.detail}
        </p>
      </section>

      {/* The equity curve is the evidence, so it gets the full width. Its axis
          numbers were raw floats and meant nothing next to the figures above. */}
      {payload.visual && payload.visual.series.length > 1 && (
        <section className="-mx-5 mt-9 sm:-mx-8">
          <div className="px-5 sm:px-8">
            <h2 className={`text-[11px] uppercase tracking-[0.09em] ${MUTED}`}>
              {copy.sections.chart}
            </h2>
          </div>
          <div className="mt-4">
            <ReceiptChart visual={payload.visual} />
          </div>
          <div
            className={`mt-3 flex justify-between px-5 text-[11.5px] tabular-nums sm:px-8 ${MUTED}`}
          >
            <span>
              {formatReceiptDate(payload.date_range.start, language) ??
                payload.date_range.start}
            </span>
            <span>
              {formatReceiptDate(payload.date_range.end, language) ??
                payload.date_range.end}
            </span>
          </div>
        </section>
      )}

      <section className="mt-10">
        <h2 className={`text-[11px] uppercase tracking-[0.09em] ${MUTED}`}>
          {copy.plan.heading}
        </h2>
        <div className="mt-3 flex flex-col gap-1.5">
          {plan.sentences.map((sentence) => (
            <p key={sentence} className="text-[16px] leading-[1.5] text-white/90">
              {sentence}
            </p>
          ))}
        </div>
        <dl className="mt-6 grid grid-cols-2 gap-x-5 gap-y-4 sm:grid-cols-3">
          {payload.symbols.length > 0 && (
            <Stat label={copy.fields.asset} value={payload.symbols.join(", ")} />
          )}
          {payload.asset_class && (
            <Stat
              label={copy.fields.asset_class}
              value={copy.asset_class_values[payload.asset_class]}
            />
          )}
          {drawdown && (
            <Stat label={metricLabel(drawdown)} value={drawdown.value} />
          )}
        </dl>
      </section>

      {payload.owner_note && (
        <blockquote className="mt-10 border-l-2 border-white/15 pl-4 text-[15px] leading-relaxed text-white/70">
          {payload.owner_note}
        </blockquote>
      )}

      <TryArgusCallToAction
        headline={copy.cta.headline}
        detail={copy.cta.detail}
        action={copy.cta.action}
      />

      {/* Complete, and secondary. Everything the earlier version put on the front
          page lives here, styled as the design system asks: visible, muted, and
          clearly not the result. */}
      <section className="mt-14 border-t border-white/10 pt-6">
        <h2 className={`text-[11px] uppercase tracking-[0.09em] ${MUTED}`}>
          {copy.fine_print.heading}
        </h2>

        {plan.settings.length > 0 && (
          <div className="mt-4">
            <p className={`${FINE} text-white/40`}>{copy.fine_print.settings}</p>
            <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1.5">
              {plan.settings.map((fact) => (
                <div key={fact.key} className="flex items-baseline gap-1.5">
                  <dt className={`${FINE} text-white/40`}>
                    {copy.strategy_facts[fact.key] ?? fact.key}
                  </dt>
                  <dd className={`${FINE} tabular-nums text-white/70`}>
                    {fact.value}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        )}

        {payload.assumptions.length > 0 && (
          <div className="mt-5">
            <p className={`${FINE} text-white/40`}>{copy.fine_print.assumed}</p>
            <ul
              lang={frozenLang}
              className={`mt-2 flex flex-col gap-1 ${FINE} text-white/60`}
            >
              {payload.assumptions.map((assumption) => (
                <li key={assumption}>{assumption}</li>
              ))}
            </ul>
          </div>
        )}

        {payload.benchmark_note && (
          <p lang={frozenLang} className={`mt-5 ${FINE} text-white/50`}>
            {payload.benchmark_note}
          </p>
        )}

        <p className={`mt-5 ${FINE} text-white/35`}>
          {frozenDate
            ? interpolate(copy.frozen_note, { date: frozenDate })
            : copy.frozen_note_undated}
        </p>
      </section>
    </main>
  );
}
