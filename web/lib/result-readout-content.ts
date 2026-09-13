/** The only public prose envelope for immutable backtest readouts. */
export type ResultReadoutContent = {
  schema_version: "result_readout/v1";
  surface: "quick_take" | "breakdown";
  language: "en" | "es-419";
  text: string | null;
};

const fields = new Set(["schema_version", "surface", "language", "text"]);

function parseReadoutContent(value: unknown): ResultReadoutContent | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  const keys = Object.keys(record);
  if (keys.length !== fields.size || keys.some((key) => !fields.has(key))
    || record.schema_version !== "result_readout/v1"
    || (record.surface !== "quick_take" && record.surface !== "breakdown")
    || (record.language !== "en" && record.language !== "es-419")
    || (record.text !== null && (typeof record.text !== "string" || !record.text.trim()))) return null;
  return {
    schema_version: record.schema_version,
    surface: record.surface,
    language: record.language,
    text: record.text,
  };
}

/** A present invalid root cannot fall through to a different card draft. */
export function resultReadoutContentFromMetadata(
  value: unknown,
  cardContent?: ResultReadoutContent | null,
): ResultReadoutContent | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  return Object.hasOwn(record, "result_readout_content")
    ? parseReadoutContent(record.result_readout_content)
    : parseReadoutContent(cardContent);
}

/** Read-time language matching never translates or changes saved text. */
export function resultReadoutText(
  value: unknown,
  surface: ResultReadoutContent["surface"],
  locale: string,
): string | null {
  const readout = parseReadoutContent(value);
  const base = locale.trim().toLowerCase().split(/[-_]/)[0];
  const language = base === "en" ? "en" : base === "es" ? "es-419" : null;
  return readout?.surface === surface && readout.language === language ? readout.text : null;
}
