import type { PublicReceiptPayload } from "@/lib/public-receipt-contract";
import {
  formatReceiptDate,
  interpolate,
  type ReceiptCopy,
} from "@/lib/receipt-copy";
import type { ArgusLanguage } from "@/lib/language-features";
import ProvenanceMark from "./ProvenanceMark";
import ReceiptChart from "./ReceiptChart";
import TryArgusCallToAction from "./TryArgusCallToAction";

type ReceiptBodyProps = {
  payload: PublicReceiptPayload;
  createdAt: string | null;
  copy: ReceiptCopy;
  language: ArgusLanguage;
};

const LABEL_CLASS =
  "text-[11.5px] font-medium uppercase tracking-[0.07em] text-black/40 dark:text-white/40";
const VALUE_CLASS = "mt-1 text-[14px] leading-snug text-black dark:text-white";

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className={LABEL_CLASS}>{label}</dt>
      <dd className={VALUE_CLASS}>{value}</dd>
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
  const assetClassLabel = payload.asset_class
    ? copy.asset_class_values[payload.asset_class]
    : null;
  // Frozen prose keeps the language it was written in. Marking it lets a screen
  // reader pronounce it correctly when the chrome around it is another language.
  const frozenLang = payload.content_language;

  return (
    <main className="mx-auto flex w-full max-w-[560px] flex-col gap-5 px-4 pb-14 pt-7 sm:px-6 sm:pt-10">
      <header className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-3">
          <span className={LABEL_CLASS}>{copy.eyebrow}</span>
          <ProvenanceMark label={copy.provenance} />
        </div>
        <h1
          lang={frozenLang}
          className="font-display text-[22px] font-semibold leading-tight text-black dark:text-white sm:text-[26px]"
        >
          {payload.idea_title}
        </h1>
      </header>

      <section
        aria-label={copy.framing.headline}
        className="rounded-2xl border border-[#c2a44d]/35 bg-[#c2a44d]/[0.09] px-4 py-3.5"
      >
        <p className="text-[14px] font-semibold leading-snug text-black dark:text-white">
          {copy.framing.headline}
        </p>
        <p className="mt-1.5 text-[13px] leading-relaxed text-black/65 dark:text-white/65">
          {copy.framing.detail}
        </p>
      </section>

      {payload.metrics.length > 0 && (
        <section className="rounded-2xl border border-black/[0.08] px-4 py-4 dark:border-white/[0.10]">
          <h2 className={LABEL_CLASS}>{copy.sections.result}</h2>
          <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3.5">
            {payload.metrics.map((metric) => (
              <div key={metric.key}>
                <dt className="text-[12px] leading-snug text-black/50 dark:text-white/50">
                  {metric.label}
                </dt>
                <dd className="font-display mt-0.5 text-[17px] font-semibold tabular-nums text-black dark:text-white">
                  {metric.value}
                </dd>
              </div>
            ))}
          </dl>
          {payload.benchmark_note && (
            <p
              lang={frozenLang}
              className="mt-3.5 text-[12.5px] leading-relaxed text-black/50 dark:text-white/50"
            >
              {payload.benchmark_note}
            </p>
          )}
        </section>
      )}

      {payload.visual && payload.visual.series.length > 1 && (
        <section className="rounded-2xl border border-black/[0.08] px-3 py-4 dark:border-white/[0.10]">
          <h2 className={`${LABEL_CLASS} px-1`}>{copy.sections.chart}</h2>
          <div className="mt-2">
            <ReceiptChart visual={payload.visual} />
          </div>
        </section>
      )}

      <section className="rounded-2xl border border-black/[0.08] px-4 py-4 dark:border-white/[0.10]">
        <h2 className={LABEL_CLASS}>{copy.sections.what_was_tested}</h2>
        <dl className="mt-3 flex flex-col gap-3.5">
          {payload.symbols.length > 0 && (
            <Field label={copy.fields.asset} value={payload.symbols.join(", ")} />
          )}
          {assetClassLabel && (
            <Field label={copy.fields.asset_class} value={assetClassLabel} />
          )}
          {payload.strategy_label && (
            <div>
              <dt className={LABEL_CLASS}>{copy.fields.strategy}</dt>
              <dd lang={frozenLang} className={VALUE_CLASS}>
                {payload.strategy_label}
              </dd>
            </div>
          )}
          <Field label={copy.fields.dates} value={payload.date_range.display} />
          {payload.benchmark_symbol && (
            <Field
              label={copy.fields.benchmark}
              value={payload.benchmark_symbol}
            />
          )}
        </dl>
      </section>

      {payload.assumptions.length > 0 && (
        <section className="rounded-2xl border border-black/[0.08] px-4 py-4 dark:border-white/[0.10]">
          <h2 className={LABEL_CLASS}>{copy.sections.assumptions}</h2>
          <ul
            lang={frozenLang}
            className="mt-2.5 flex flex-col gap-1.5 text-[13.5px] leading-relaxed text-black/65 dark:text-white/65"
          >
            {payload.assumptions.map((assumption) => (
              <li key={assumption} className="flex gap-2">
                <span aria-hidden="true" className="text-black/30 dark:text-white/30">
                  •
                </span>
                <span>{assumption}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {payload.owner_note && (
        <section className="rounded-2xl border border-black/[0.08] px-4 py-4 dark:border-white/[0.10]">
          <h2 className={LABEL_CLASS}>{copy.sections.note}</h2>
          <p className="mt-2 text-[13.5px] leading-relaxed text-black/70 dark:text-white/70">
            {payload.owner_note}
          </p>
        </section>
      )}

      <p className="text-[12px] leading-relaxed text-black/40 dark:text-white/40">
        {frozenDate
          ? interpolate(copy.frozen_note, { date: frozenDate })
          : copy.frozen_note_undated}
      </p>

      <TryArgusCallToAction
        headline={copy.cta.headline}
        detail={copy.cta.detail}
        action={copy.cta.action}
      />
    </main>
  );
}
