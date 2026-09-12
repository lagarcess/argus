import { researchSourcesFromFacts } from "./chat-discovery-sidecar";
import { parseEvidenceVisual, type EvidenceVisual } from "./evidence-visual";
import type { Message } from "@/components/chat/types";
import type { ApiMessage } from "./argus-api";

export type ToolScalar = string | number | boolean | null;
export type LocalizedToolText = { locale_key: string; interpolation_args: Record<string, ToolScalar> };
export type ToolProgress = LocalizedToolText & { call_id: string; tool_name: string };
/** Where a fact came from; older cards carry none and stay readable. */
export type ToolFactSource = { kind: "user" | "page" | "computed" | "not_found"; title?: string | null; url?: string | null; date?: string | null };
export type ToolFact = { name: string; label: LocalizedToolText; value: ToolScalar; unit: LocalizedToolText | null; value_text?: LocalizedToolText | null; source?: ToolFactSource | null };
export type ToolInputFact = ToolFact & { editable: boolean; unknown: boolean; visibility?: "public" | "private" };
export type ToolResearchSource = { url: string; title: string; source_date?: string | null };
export type ToolCardPresentation = {
  title: LocalizedToolText; answer: ToolFact | null; rows: ToolFact[];
  inputs: ToolInputFact[]; notes: LocalizedToolText[];
  narrative?: string | null; sources?: ToolResearchSource[];
  visual?: EvidenceVisual | null;
};
/** A typed fix the user can tap: an argument edit the recompute route accepts. */
export type ToolRepair = { kind: "set_inputs"; label: LocalizedToolText; changes: Record<string, ToolScalar> };
export type ToolFailure = { code: string; fields: string[]; repair?: ToolRepair | null };
export type ToolOutcome = {
  status: "succeeded" | "invalid" | "ambiguous" | "bounded" | "unavailable";
  result: Record<string, unknown> | null;
  failure: ToolFailure | null;
};
export type ToolResultCard = {
  kind: "tool_result"; schema_version: 1; tool_name: string; call_id: string;
  artifact_id: string; input_revision: number; card_type: string; card_version: 1;
  arguments: Record<string, unknown>; outcome: ToolOutcome;
  presentation: ToolCardPresentation; artifact_state: "active" | "superseded" | "consumed" | "cancelled";
};
export type ToolTranslator = (key: string, values?: Record<string, unknown>) => string;
export type ToolRecompute = (card: ToolResultCard, changes: Record<string, ToolScalar>) => Promise<void>;

const record = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === "string" && value.length > 0;
const scalar = (value: unknown): value is ToolScalar =>
  value === null || typeof value === "string" || typeof value === "boolean" ||
  (typeof value === "number" && Number.isFinite(value));

function localized(value: unknown): value is LocalizedToolText {
  return record(value) && text(value.locale_key) && record(value.interpolation_args) &&
    Object.values(value.interpolation_args).every(scalar);
}
const SOURCE_KINDS = new Set(["user", "page", "computed", "not_found"]);
function source(value: unknown): value is ToolFactSource {
  if (!record(value) || !SOURCE_KINDS.has(String(value.kind))) return false;
  return ["title", "url", "date"].every((key) => value[key] == null || typeof value[key] === "string");
}
function repair(value: unknown): value is ToolRepair {
  return record(value) && value.kind === "set_inputs" && localized(value.label) && record(value.changes) &&
    Object.keys(value.changes).length > 0 && Object.values(value.changes).every(scalar);
}
function fact(value: unknown): value is ToolFact {
  return record(value) && text(value.name) && localized(value.label) && scalar(value.value) &&
    (value.unit === null || localized(value.unit)) && (value.value_text == null || localized(value.value_text)) &&
    (value.source == null || source(value.source));
}
export function parseToolPresentation(value: unknown): ToolCardPresentation | null {
  if (!record(value) || !localized(value.title) || !(value.answer === null || fact(value.answer)) ||
    !Array.isArray(value.rows) || !value.rows.every(fact) ||
    !Array.isArray(value.notes) || !value.notes.every(localized) ||
    !Array.isArray(value.inputs) || !value.inputs.every((input) =>
      record(input) && typeof input.editable === "boolean" &&
      typeof input.unknown === "boolean" &&
      !(input.unknown && (input.value !== null || input.editable)) &&
      (input.visibility === undefined || input.visibility === "public" || input.visibility === "private") && fact(input))) return null;
  if (value.narrative != null && typeof value.narrative !== "string") return null;
  if (value.sources !== undefined && (!Array.isArray(value.sources) || researchSourcesFromFacts(value.sources).length !== value.sources.length)) return null;
  if (value.visual != null && !parseEvidenceVisual(value.visual)) return null;
  const inputs = value.inputs as ToolInputFact[];
  if (new Set(inputs.map((input) => input.name)).size !== inputs.length) return null;
  return value as ToolCardPresentation;
}
export function parseToolProgress(value: unknown): ToolProgress | null {
  return record(value) && text(value.call_id) && text(value.tool_name) && localized(value)
    ? value as ToolProgress : null;
}
export function parseToolResultCard(value: unknown): ToolResultCard | null {
  if (!record(value) || value.kind !== "tool_result" || value.schema_version !== 1 ||
    value.card_version !== 1 || !text(value.card_type) || !text(value.tool_name) ||
    !text(value.call_id) || !text(value.artifact_id) || !Number.isInteger(value.input_revision) ||
    (value.input_revision as number) < 0 || !record(value.arguments) ||
    !["active", "superseded", "consumed", "cancelled"].includes(String(value.artifact_state))) return null;
  const presentation = parseToolPresentation(value.presentation);
  const outcome = value.outcome;
  if (!presentation || !record(outcome)) return null;
  if (outcome.status === "succeeded") {
    if (!record(outcome.result) || outcome.failure !== null) return null;
  } else if (!["invalid", "ambiguous", "bounded", "unavailable"].includes(String(outcome.status)) ||
    outcome.result !== null || !record(outcome.failure) || !text(outcome.failure.code) ||
    !Array.isArray(outcome.failure.fields) || !outcome.failure.fields.every(text) ||
    (outcome.failure.repair != null && !repair(outcome.failure.repair)) ||
    presentation.answer !== null || presentation.narrative != null || presentation.visual != null) return null;
  return value as ToolResultCard;
}

/** Both live finals and durable message readers enter through this parser. */
export function toolCardsFromMetadata(metadata: Record<string, unknown>): ToolResultCard[] {
  const nested = record(metadata.final_response_payload) ? metadata.final_response_payload : null;
  const cards = metadata.tool_result_cards ?? nested?.tool_result_cards;
  if (!Array.isArray(cards)) return [];
  const parsed = cards.map(parseToolResultCard).filter((card): card is ToolResultCard => card !== null);
  const seen = new Set<string>();
  return parsed.filter((card) => !seen.has(card.artifact_id) && Boolean(seen.add(card.artifact_id)));
}

export function hasUnavailableToolCards(metadata: Record<string, unknown>): boolean {
  const nested = record(metadata.final_response_payload) ? metadata.final_response_payload : null;
  const value = metadata.tool_result_cards ?? nested?.tool_result_cards;
  return value != null && (!Array.isArray(value) || value.length > toolCardsFromMetadata(metadata).length);
}

export function toolCardCopyText(card: ToolResultCard, t: ToolTranslator, locale: string): string {
  const { presentation } = card;
  const facts = [presentation.answer, ...presentation.rows, ...presentation.inputs].filter((value): value is ToolFact => value !== null);
  return [localizedToolText(presentation.title, t), presentation.narrative ?? "", ...facts.map((value) =>
    `${localizedToolText(value.label, t)}: ${toolFactValue(value, t, locale)}`),
  ...presentation.notes.map((note) => localizedToolText(note, t)),
  ...researchSourcesFromFacts(presentation.sources).map((source) => `${source.title || source.domain}: ${source.url}`)].filter(Boolean).join("\n");
}

export function localizedToolText(value: LocalizedToolText, t: ToolTranslator): string {
  const rendered = t(value.locale_key, { ...value.interpolation_args, defaultValue: "" });
  return rendered && rendered !== value.locale_key ? rendered : t("tools.card.unavailable");
}
export function toolProgressText(value: ToolProgress | null, t: ToolTranslator): string {
  if (!value) return t("chat.status.working");
  const rendered = t(value.locale_key, { ...value.interpolation_args, defaultValue: "" });
  return rendered && rendered !== value.locale_key ? rendered : t("chat.status.working");
}
export function toolFactValue(value: ToolFact, t: ToolTranslator, locale: string): string {
  const content = value.value_text ? localizedToolText(value.value_text, t) : value.value === null ? t("tools.card.unknown") :
    typeof value.value === "number" ? new Intl.NumberFormat(locale, { maximumFractionDigits: 20 }).format(value.value) :
    typeof value.value === "boolean" ? t(value.value ? "tools.card.yes" : "tools.card.no") : value.value;
  return value.unit ? `${content} ${localizedToolText(value.unit, t)}` : content;
}

/** The provenance line under an input: stated, cited with its date, or computed. */
export function toolFactSourceText(fact: ToolFact, t: ToolTranslator, locale: string): string | null {
  const provenance = fact.source;
  if (!provenance) return null;
  if (provenance.kind === "page") {
    const date = provenance.date ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: "UTC" }).format(new Date(`${provenance.date}T00:00:00Z`)) : "";
    const title = provenance.title?.trim() || (provenance.url ? safeHost(provenance.url) : "");
    return title && date ? t("tools.card.source.page_dated", { title, date }) : t("tools.card.source.page", { title: title || date });
  }
  return t(`tools.card.source.${provenance.kind}`, { defaultValue: "" }) || null;
}
function safeHost(url: string): string {
  try { return new URL(url).hostname; } catch { return ""; }
}
/** A blank the user can fill: an input no source supplied, never the retained unknown. */
export function toolInputAwaitsValue(input: ToolInputFact): boolean {
  return input.editable && !input.unknown && input.value === null;
}

/** Transport conversion only. Domain validation and every calculation stay in Python. */
export function toolInputChange(card: ToolResultCard, name: string, raw: string): Record<string, ToolScalar> | null {
  const input = card.presentation.inputs.find((candidate) => candidate.name === name);
  if (card.artifact_state !== "active" || !input?.editable || input.unknown || raw.trim() === "") return null;
  let value: ToolScalar = raw;
  if (typeof input.value === "number" || (input.value === null && Number.isFinite(Number(raw)) && raw.trim() !== "")) {
    value = Number(raw);
    if (!Number.isFinite(value)) return null;
  } else if (typeof input.value === "boolean") {
    if (raw !== "true" && raw !== "false") return null;
    value = raw === "true";
  }
  return { [name]: value };
}

export function toolInputChanges(card: ToolResultCard, drafts: Record<string, string>): Record<string, ToolScalar> | null {
  const changes: Record<string, ToolScalar> = {};
  for (const [name, raw] of Object.entries(drafts)) {
    const parsed = toolInputChange(card, name, raw);
    if (!parsed) return null;
    if (parsed[name] !== card.arguments[name]) changes[name] = parsed[name];
  }
  return changes;
}

/** Per-artifact monotonic revisions also protect sibling cards in a plural message. */
export function applyToolResultMessage(messages: Message[], response: ApiMessage): Message[] {
  const updates = toolCardsFromMetadata(response.metadata ?? {});
  return messages.map((message) => {
    if (message.id !== response.id) return message;
    return { ...message, toolResultCards: (message.toolResultCards ?? []).map((current) => {
      const update = updates.find((candidate) => candidate.artifact_id === current.artifact_id &&
        candidate.call_id === current.call_id && candidate.tool_name === current.tool_name);
      return update && update.input_revision > current.input_revision ? update : current;
    }) };
  });
}
