import { headlineReceiptMetric } from "./public-receipt-contract";
import { isSelectedReceiptDocument, type PublicReceiptDocument } from "./public-receipt-turns";
import type { ArgusLanguage } from "./language-features";
import { receiptCopy, formatReceiptDateRange, formatReceiptDate, interpolate } from "./receipt-copy";
import { receiptPresentations } from "./receipt-presentation";

/** Only approved frozen fields can feed SSR metadata or its image. */
export function receiptPreviewFacts(payload: PublicReceiptDocument, language: ArgusLanguage) {
  const copy = receiptCopy(language);
  const presentation = receiptPresentations(payload, null, language)[0];
  const first = isSelectedReceiptDocument(payload) ? payload.turns[0] : null;
  const count = isSelectedReceiptDocument(payload) ? payload.turns.length : 1;
  const countText = count > 1 ? interpolate(copy.selection.turns, { count }) : null;
  const research = first?.kind === "research_answer" ? first : null;
  const stamp = research ? interpolate(copy.research.preview_stamp, { date: formatReceiptDate(research.retrieved_at, language) ?? "", count: research.sources.length }) : null;
  const headline = payload.schema_version === 1 ? headlineReceiptMetric(payload) : null;
  const framing = presentation.toolCards ? presentation.framing : research ? copy.research.short : copy.framing.short;
  const description = payload.schema_version === 1 ? [
    payload.symbols.join(", "), formatReceiptDateRange(payload.date_range, copy, language),
    headline ? `${copy.metric_labels[headline.key] ?? headline.key}: ${headline.value}` : null, copy.framing.short,
  ].filter(Boolean).join(" · ") : [
    research ? stamp : presentation.rows.map((row) => row.value).join(" · "),
    countText, framing,
  ].filter(Boolean).join(" · ");
  return {
    title: presentation.title, language: presentation.language, description,
    provenance: presentation.provenance ?? copy.provenance,
    metricValue: headline?.value ?? presentation.headline ?? "", verdict: presentation.verdict ?? "",
    research: Boolean(research), stamp, countText,
    imageTitle: presentation.title.length > 130 ? `${presentation.title.slice(0, 127).trimEnd()}...` : presentation.title,
    framing,
  };
}
