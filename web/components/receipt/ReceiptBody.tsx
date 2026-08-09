import type { PublicReceiptPayload } from "@/lib/public-receipt-contract";
import { type ReceiptCopy } from "@/lib/receipt-copy";
import {
  benchmarkReturn,
  benchmarkVerdict,
  receiptPlan,
} from "@/lib/receipt-plan";
import type { ArgusLanguage } from "@/lib/language-features";
import { formatReceiptDate } from "@/lib/receipt-copy";
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
 * The shared page: a dated record, read once.
 *
 * Ruled rows and a record stamp rather than bordered cards, because the form has to
 * argue for the numbers on a page nobody arrived at through Argus. Everything in it
 * appears once: the date is in the stamp and not repeated in the fine print, the
 * benchmark is in the headline and not restated underneath, and the rules list only
 * the rules that exist.
 */
const LABEL = "text-[10.5px] uppercase tracking-[0.1em] text-white/40";
const RULE = "border-t border-white/10";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className={`flex items-baseline justify-between gap-3 py-2 ${RULE}`}>
      <dt className="text-[11.5px] text-white/45">{label}</dt>
      <dd className="font-display text-[13.5px] tabular-nums text-white/90">
        {value}
      </dd>
    </div>
  );
}

export default function ReceiptBody({
  payload,
  createdAt,
  copy,
  language,
}: ReceiptBodyProps) {
  const stamped = formatReceiptDate(createdAt, language);
  const frozenLang = payload.content_language;
  const plan = receiptPlan(payload, copy);
  const verdict = benchmarkVerdict(payload, copy);
  const benchmark = benchmarkReturn(payload);

  const metric = (...keys: string[]) =>
    payload.metrics.find((entry) => keys.includes(entry.key)) ?? null;
  // Metric labels are frozen in English inside the payload. For the keys Argus owns
  // the label renders in the viewer's language instead, as the strategy facts do.
  const metricLabel = (entry: { key: string; label: string }) =>
    (copy.metric_labels as Record<string, string>)[entry.key] ?? entry.label;
  const headline = metric("total_return_pct", "total_return");
  const drawdown = metric("max_drawdown_pct", "max_drawdown");
  const isNegative = Boolean(headline?.value.trim().startsWith("-"));

  return (
    <main className="mx-auto flex w-full max-w-[620px] flex-col px-5 pb-16 pt-5 sm:px-8 sm:pt-9">
      <ReceiptViewBeacon />

      <div className="flex items-center justify-between gap-3">
        <ProvenanceMark label={copy.provenance} />
        {stamped && <span className={LABEL}>{stamped}</span>}
      </div>

      <h1
        lang={frozenLang}
        className="font-display mt-4 text-[23px] font-medium leading-[1.16] tracking-[-0.5px] text-white sm:text-[30px] sm:tracking-[-0.8px]"
      >
        {payload.idea_title}
      </h1>

      <div className={`mt-4 pt-5 ${RULE}`}>
        <div
          className={`font-display text-[52px] font-medium leading-[0.98] tracking-[-1.9px] tabular-nums sm:text-[62px] sm:tracking-[-2.4px] ${
            isNegative ? "text-[#d66d75]" : "text-[#5ba897]"
          }`}
        >
          {headline?.value}
        </div>
        {verdict && (
          <p className="font-display mt-2.5 text-[15px] font-medium tabular-nums text-white">
            {verdict}
            {benchmark && payload.benchmark_symbol && (
              <span className="font-medium text-white/45">
                {" · "}
                {payload.benchmark_symbol} {benchmark}
              </span>
            )}
          </p>
        )}

        <dl className="mt-4">
          {payload.symbols.length > 0 && (
            <Row
              label={copy.fields.asset}
              value={
                payload.asset_class
                  ? `${payload.symbols.join(", ")} · ${copy.asset_class_values[payload.asset_class]}`
                  : payload.symbols.join(", ")
              }
            />
          )}
          <Row label={copy.fields.dates} value={payload.date_range.display} />
          {drawdown && (
            <Row label={metricLabel(drawdown)} value={drawdown.value} />
          )}
        </dl>
      </div>

      {payload.visual && payload.visual.series.length > 1 && (
        <div className={`mt-4 -mx-5 pt-4 sm:-mx-8 ${RULE}`}>
          <ReceiptChart visual={payload.visual} />
        </div>
      )}

      {/* Only the rules that exist. A strategy that never sells says so and stops. */}
      <section className={`mt-4 pt-5 ${RULE}`}>
        <h2 className="text-[10px] font-medium uppercase tracking-[0.1em] text-[#5ba897]">
          {copy.plan.heading}
        </h2>
        <div className="mt-2.5 flex flex-col">
          {plan.rows.map((row, index) => (
            <div
              key={row.text}
              className={index === 0 ? "pb-2.5" : `py-2.5 ${RULE}`}
            >
              <p className="text-[14px] leading-[1.45] text-white">{row.text}</p>
              {row.exact && (
                <p className="mt-1 text-[11px] tabular-nums tracking-[0.02em] text-white/40">
                  {row.exact}
                </p>
              )}
            </div>
          ))}
        </div>
        {payload.assumptions.length > 0 && (
          <ul
            lang={frozenLang}
            className="mt-3.5 flex flex-col gap-1 text-[11.5px] leading-[1.5] text-white/40"
          >
            {payload.assumptions.map((assumption) => (
              <li key={assumption}>{assumption}</li>
            ))}
          </ul>
        )}
        <p className="mt-2 text-[11.5px] leading-[1.5] text-white/40">
          {copy.plan.long_only}
        </p>
      </section>

      {payload.owner_note && (
        <blockquote className="mt-6 border-l-2 border-white/15 pl-4 text-[14px] leading-relaxed text-white/70">
          {payload.owner_note}
        </blockquote>
      )}

      <div className={`mt-5 pt-4 ${RULE}`}>
        <p className="text-[12.5px] leading-relaxed text-[#c2a44d]">
          {copy.framing.headline} {copy.framing.detail}
        </p>
      </div>

      <TryArgusCallToAction
        headline={copy.cta.headline}
        detail={copy.cta.detail}
        action={copy.cta.action}
      />
    </main>
  );
}
