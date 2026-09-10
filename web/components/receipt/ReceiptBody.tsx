import { Fragment } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { PublicReceiptDocument } from "@/lib/public-receipt-turns";
import { receiptDocumentKind } from "@/lib/public-receipt-turns";
import { type ReceiptCopy, formatReceiptDay, interpolate, receiptTranslator } from "@/lib/receipt-copy";
import ToolCardPresentation from "@/components/chat/ToolCardPresentation";
import { receiptPresentations } from "@/lib/receipt-presentation";
import type { ArgusLanguage } from "@/lib/language-features";
import { RECEIPT_ACTION_BAR_CLEARANCE } from "@/lib/receipt-layout";
import ProvenanceMark from "./ProvenanceMark";
import ReceiptActionBar from "./ReceiptActionBar";
import ReceiptChart from "./ReceiptChart";
import ReceiptViewBeacon from "./ReceiptViewBeacon";

type ReceiptBodyProps = {
  payload: PublicReceiptDocument;
  createdAt: string | null;
  copy: ReceiptCopy;
  language: ArgusLanguage;
  preview?: boolean;
};

const LABEL = "text-[10.5px] uppercase tracking-[0.1em] text-white/40";
const RULE = "border-t border-white/10";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className={`flex items-baseline justify-between gap-3 py-2 ${RULE}`}>
      <dt className="text-[11.5px] text-white/45">{label}</dt>
      <dd className="font-display text-[13.5px] tabular-nums text-white/90">{value}</dd>
    </div>
  );
}

/** One receipt form, fed by the shared presentation projection for every kind. */
export default function ReceiptBody({ payload, createdAt, copy, language, preview = false }: ReceiptBodyProps) {
  const entries = receiptPresentations(payload, createdAt, language);
  const kind = receiptDocumentKind(payload);
  return (
    <>
      <main className={`mx-auto flex w-full max-w-[620px] flex-col px-5 pt-5 sm:px-8 sm:pt-9 ${preview ? "pb-8" : RECEIPT_ACTION_BAR_CLEARANCE}`}>
        {!preview && <ReceiptViewBeacon kind={kind} />}
        {entries.length > 1 && <p className={`mb-4 ${LABEL}`}>{interpolate(copy.selection.turns, { count: entries.length })}</p>}
        {entries.map((entry, index) => {
          const Heading = index === 0 ? "h1" : "h2";
          const isNegative = Boolean(entry.headline?.trim().startsWith("-"));
          return (
            <Fragment key={index}>
              {index > 0 && <hr className="my-10 border-white/20" />}
              <div className={entry.research ? "flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between" : "flex items-center justify-between gap-3"}>
                <ProvenanceMark label={entry.provenance ?? copy.provenance} />
                {entry.stamp && <span className={LABEL}>{entry.stamp}</span>}
              </div>
              {!entry.hideTitle && <Heading lang={entry.language} className="font-display mt-4 text-[23px] font-medium leading-[1.16] tracking-[-0.5px] text-white sm:text-[30px] sm:tracking-[-0.8px]">{entry.title}</Heading>}
              {entry.toolCards && <section data-receipt-tool-cards className="dark mt-5 space-y-7 text-white">
                {entry.toolCards.map((card, cardIndex) => <div key={cardIndex}>
                  <ToolCardPresentation presentation={card.presentation} t={receiptTranslator(language)} locale={language} />
                </div>)}
              </section>}
              {!entry.research && !entry.toolCards && (
                <div className={`mt-4 pt-5 ${RULE}`}>
                  <div className={`font-display text-[52px] font-medium leading-[0.98] tracking-[-1.9px] tabular-nums sm:text-[62px] sm:tracking-[-2.4px] ${isNegative ? "text-[#d66d75]" : "text-[#5ba897]"}`}>{entry.headline}</div>
                  {entry.verdict && (
                    <p className="font-display mt-2.5 text-[15px] font-medium tabular-nums text-white">
                      {entry.verdict}
                      {entry.benchmark && entry.benchmarkSymbol && <span className="font-medium text-white/45">{" · "}{entry.benchmarkSymbol} {entry.benchmark}</span>}
                    </p>
                  )}
                  <dl className="mt-4">{entry.rows.map((row) => <Row key={row.label} {...row} />)}</dl>
                </div>
              )}
              {entry.research && (
                <>
                  <div lang={entry.language} className={`mt-4 min-w-0 pt-5 text-[15px] leading-relaxed text-white/90 [&_p]:mb-4 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-1 [&_h2]:my-4 [&_h2]:font-medium [&_h3]:my-3 [&_h3]:font-medium [&_a]:underline [&_a]:underline-offset-4 ${RULE}`}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml allowedElements={["p", "strong", "em", "ul", "ol", "li", "a", "blockquote", "h2", "h3", "br", "code", "table", "thead", "tbody", "tr", "th", "td"]} unwrapDisallowed components={{
                      a: ({ children, href }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
                      table: ({ children }) => <div className="my-4 max-w-full overflow-x-auto"><table className="w-full border-collapse text-left text-[13px] leading-relaxed [&_th]:border-b [&_th]:border-white/20 [&_th]:px-3 [&_th]:py-2 [&_th]:font-medium [&_td]:border-b [&_td]:border-white/10 [&_td]:px-3 [&_td]:py-2 [&_td]:align-top">{children}</table></div>,
                    }}>{entry.research.answer}</ReactMarkdown>
                  </div>
                  <section className={`mt-4 pt-5 ${RULE}`}>
                    <h2 className={LABEL}>{copy.research.sources}</h2>
                    <ul className="mt-3">
                      {entry.research.sources.map((source) => <li key={source.url} className={`py-3 ${RULE}`}>
                        <a href={source.url} target="_blank" rel="noopener noreferrer" lang={entry.language} className="text-[14px] leading-relaxed text-white underline decoration-white/30 underline-offset-4">{source.title}</a>
                        <p className="mt-1 text-[12px] text-white/45">{[source.domain, formatReceiptDay(source.source_date, language)].filter(Boolean).join(" · ")}</p>
                      </li>)}
                    </ul>
                  </section>
                  {entry.research.nextStep && <section className={`mt-4 pt-5 ${RULE}`}><h2 className={LABEL}>{copy.research.next_step}</h2><p className="mt-2 text-[14px] leading-relaxed text-white/70">{entry.research.nextStep}</p></section>}
                </>
              )}
              {entry.visual && entry.visual.series.length > 1 && <div className={`mt-4 -mx-5 pt-4 sm:-mx-8 ${RULE}`}><ReceiptChart visual={entry.visual} /></div>}
              {entry.plan && (
                <section className={`mt-4 pt-5 ${RULE}`}>
                  <h2 className="text-[10px] font-medium uppercase tracking-[0.1em] text-[#5ba897]">{entry.plan.heading}</h2>
                  <div className="mt-2.5 flex flex-col">
                    {entry.plan.rows.map((row, rowIndex) => <div key={row.text} className={rowIndex === 0 ? "pb-2.5" : `py-2.5 ${RULE}`}>
                      <p className="text-[14px] leading-[1.45] text-white">{row.text}</p>
                      {row.exact && <p className="mt-1 text-[11px] tabular-nums tracking-[0.02em] text-white/40">{row.exact}</p>}
                    </div>)}
                  </div>
                  {entry.plan.assumptions.length > 0 && <ul className="mt-3.5 flex flex-col gap-1 text-[11.5px] leading-[1.5] text-white/40">{entry.plan.assumptions.map((assumption) => <li key={assumption}>{assumption}</li>)}</ul>}
                  {entry.plan.footer && <p className="mt-2 text-[11.5px] leading-[1.5] text-white/40">{entry.plan.footer}</p>}
                </section>
              )}
              {entry.ownerNote && <blockquote lang={payload.schema_version === 1 ? undefined : entry.language} className="mt-6 border-l-2 border-white/15 pl-4 text-[14px] leading-relaxed text-white/70">{entry.ownerNote}</blockquote>}
              <div className={`mt-5 pt-4 ${RULE}`}><p className="text-[12.5px] leading-relaxed text-[#c2a44d]">{entry.framing}</p></div>
            </Fragment>
          );
        })}
      </main>
      {!preview && <ReceiptActionBar kind={kind} framing={kind === "backtest" ? copy.framing.headline : entries.some((entry) => entry.toolCards) ? receiptTranslator(language)("tools.receipt.framing") : copy.research.headline} action={copy.cta.action} />}
    </>
  );
}
