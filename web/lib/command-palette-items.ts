import type { HistoryItem, SearchItem, SearchLedgerGroup } from "./argus-api";

export type CommandPaletteDisplayItem = {
  id: string;
  type: SearchItem["type"];
  conversationId: string | null;
  title: string;
  snippet: string;
  updatedAt: string;
  source: "recent" | "search";
  lifecycle?: string | null;
  decisionState?: string | null;
  preview?: Record<string, unknown> | null;
  canManageConversation: boolean;
  activation: "open_conversation";
};

export type CommandPalettePreviewField = {
  id: string;
  labelKey: string;
  labelFallback: string;
  value: string;
};

export type CommandPaletteLedgerDisplayGroup = {
  id: string;
  decisionState: string;
  count: number;
  items: CommandPaletteDisplayItem[];
};

export type CommandPaletteItemCopy = {
  decisionStateLabel?: (state: string) => string;
  metricLabel?: (id: string, fallback: string) => string;
};

export function commandPaletteItemFromHistory(
  item: HistoryItem,
): CommandPaletteDisplayItem | null {
  if (item.type !== "chat") return null;
  return {
    id: item.id,
    type: "chat",
    conversationId: item.conversation_id ?? item.id,
    title: item.title,
    snippet: item.subtitle ?? "",
    updatedAt: item.created_at,
    source: "recent",
    lifecycle: null,
    decisionState: null,
    preview: null,
    canManageConversation: true,
    activation: "open_conversation",
  };
}

export function commandPaletteItemFromSearch(
  item: SearchItem,
  copy: CommandPaletteItemCopy = {},
): CommandPaletteDisplayItem | null {
  if (!commandPaletteSupportsSearchType(item.type)) return null;
  const conversationId =
    item.type === "chat"
      ? (item.conversation_id ?? item.id)
      : (item.conversation_id ?? null);
  return {
    id: item.id,
    type: item.type,
    conversationId,
    title: item.title,
    snippet: commandPaletteSnippet(item, copy),
    updatedAt: item.updated_at,
    source: "search",
    lifecycle: item.lifecycle ?? null,
    decisionState: item.decision_state ?? null,
    preview: safeCommandPalettePreview(item.preview),
    canManageConversation: item.type === "chat" && Boolean(conversationId),
    activation: "open_conversation",
  };
}

export function commandPaletteSelectedPreview(
  previewItem: CommandPaletteDisplayItem | null,
  displayItems: readonly CommandPaletteDisplayItem[],
): CommandPaletteDisplayItem | null {
  if (
    previewItem &&
    displayItems.some(
      (item) =>
        item.id === previewItem.id &&
        item.type === previewItem.type &&
        item.source === previewItem.source,
    )
  ) {
    return previewItem;
  }
  return displayItems[0] ?? null;
}

export function commandPaletteGroupsByLedgerState(
  items: readonly CommandPaletteDisplayItem[],
  ledgerGroups: readonly SearchLedgerGroup[],
): CommandPaletteLedgerDisplayGroup[] {
  return ledgerGroups.map((group) => ({
    id: `ledger:${group.decision_state}`,
    decisionState: group.decision_state,
    count: group.count,
    items: items.filter(
      (item) =>
        item.type === "idea" && item.decisionState === group.decision_state,
    ),
  }));
}

export function commandPaletteTypeLabelKey(type: SearchItem["type"]) {
  return `command_palette.type.${type}`;
}

export function commandPaletteTypeFallback(type: SearchItem["type"]) {
  switch (type) {
    case "backtest":
      return "Backtest";
    case "collection":
      return "Collection";
    case "decision":
      return "Decision";
    case "evidence":
      return "Evidence";
    case "idea":
      return "Idea";
    case "run":
      return "Run";
    case "strategy":
      return "Strategy";
    case "chat":
    default:
      return "Conversation";
  }
}

export function commandPaletteStatusLabelKey(item: CommandPaletteDisplayItem) {
  // Idea Ledger: a decided idea shows its decision (Promising/Rejected/...) as the
  // status pill, which is more useful than the generic "Decided" lifecycle.
  if (item.type === "idea" && item.decisionState) {
    return `chat.result_card.decision_states.${item.decisionState}`;
  }
  const status = commandPaletteStatusId(item);
  return status ? `command_palette.status.${status}` : null;
}

export function commandPaletteStatusFallback(item: CommandPaletteDisplayItem) {
  if (item.type === "idea" && item.decisionState) {
    return commandPaletteDecisionStateFallback(item.decisionState);
  }
  switch (commandPaletteStatusId(item)) {
    case "archived":
      return "Archived";
    case "captured":
      return "Captured";
    case "decided":
      return "Decided";
    case "discarded":
      return "Discarded";
    case "reviewed":
      return "Reviewed";
    case "saved":
      return "Saved";
    default:
      return null;
  }
}

export function commandPaletteOpenLabelKey(item: CommandPaletteDisplayItem) {
  return item.type === "chat"
    ? "command_palette.open_conversation"
    : "command_palette.open_source_conversation";
}

export function commandPaletteOpenFallback(item: CommandPaletteDisplayItem) {
  return item.type === "chat"
    ? "Open conversation"
    : "Open source conversation";
}

export function commandPaletteSupportsSearchType(type: SearchItem["type"]) {
  return (
    type === "chat" ||
    type === "backtest" ||
    type === "decision" ||
    type === "evidence" ||
    type === "idea"
  );
}

export function commandPaletteDecisionStateFallback(state: string) {
  switch (state) {
    case "promising":
      return "Promising";
    case "rejected":
      return "Rejected";
    case "revisit_later":
      return "Revisit later";
    case "watching":
      return "Watching";
    default:
      return "Decision";
  }
}

export function commandPalettePreviewFields(
  item: CommandPaletteDisplayItem,
  copy: CommandPaletteItemCopy = {},
): CommandPalettePreviewField[] {
  const preview = item.preview ?? {};
  const fields: CommandPalettePreviewField[] = [];
  const addField = (
    id: string,
    labelFallback: string,
    value: string | null,
  ) => {
    if (!value) return;
    fields.push({
      id,
      labelKey: `command_palette.preview_fields.${id}`,
      labelFallback,
      value,
    });
  };

  const quickTake = safePreviewString(preview.quick_take);
  const digest = safePreviewString(preview.digest);
  addField("quick_take", "Quick take", quickTake);
  if (digest && digest !== quickTake) {
    addField("digest", "Digest", digest);
  }

  const symbols = safePreviewStringList(preview.symbols);
  addField("assets", "Assets", symbols.join(", ") || null);
  addField("benchmark", "Benchmark", safePreviewString(preview.benchmark_symbol));

  if (item.type === "decision") {
    const state = safePreviewString(preview.decision_state);
    const label = state
      ? (copy.decisionStateLabel?.(state) ??
        commandPaletteDecisionStateFallback(state))
      : null;
    addField("decision", "Decision", label);
  }

  addField("metrics", "Metrics", metricsSummaryText(preview.metrics_summary, copy));

  const assumptions = safePreviewStringList(preview.assumptions);
  addField("assumptions", "Assumptions", assumptions.join(" · ") || null);

  addField("breakdown", "Breakdown", breakdownPreviewText(preview.breakdown));

  if (fields.length === 0) {
    addField("preview", "Preview", item.snippet || null);
  }
  return fields;
}

function commandPaletteStatusId(item: CommandPaletteDisplayItem) {
  const lifecycle = safePreviewString(item.lifecycle);
  switch (lifecycle) {
    case "archived":
    case "captured":
    case "decided":
    case "discarded":
    case "reviewed":
    case "saved":
      return lifecycle;
    default:
      return null;
  }
}

function commandPaletteSnippet(item: SearchItem, copy: CommandPaletteItemCopy) {
  const digest = item.preview?.digest;
  const quickTake = item.preview?.quick_take;
  if (item.type === "decision") {
    const state =
      typeof item.preview?.decision_state === "string"
        ? item.preview.decision_state
        : null;
    const stateLabel = state
      ? (copy.decisionStateLabel?.(state) ??
        commandPaletteDecisionStateFallback(state))
      : null;
    const digestText = typeof digest === "string" ? digest.trim() : "";
    return [stateLabel, digestText].filter(Boolean).join(" · ");
  }
  if (typeof quickTake === "string" && quickTake.trim()) {
    return quickTake;
  }
  if (typeof digest === "string" && digest.trim()) {
    return digest;
  }
  return item.matched_text ?? "";
}

function safeCommandPalettePreview(
  preview: Record<string, unknown> | null | undefined,
) {
  if (!preview) return null;
  const safe: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(preview)) {
    if (key.endsWith("_id")) continue;
    if (key === "context_packets" || key === "actions") continue;
    safe[key] = value;
  }
  return safe;
}

function safePreviewString(value: unknown) {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed || null;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return null;
}

function safePreviewStringList(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    const text = safePreviewString(item);
    return text ? [text] : [];
  });
}

function metricsSummaryText(value: unknown, copy: CommandPaletteItemCopy) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const summary = value as Record<string, unknown>;
  const fields: Array<[string, string]> = [
    ["total_return_pct", "Total return"],
    ["benchmark_return_pct", "Benchmark return"],
    ["delta_vs_benchmark_pct", "Against benchmark"],
    ["excess_return_pct", "Against benchmark"],
    ["max_drawdown_pct", "Worst drop"],
    ["volatility_pct", "Volatility"],
    ["sharpe_ratio", "Sharpe"],
  ];
  const parts = fields.flatMap(([key, label]) => {
    const raw = summary[key];
    const formatted = formatMetricValue(key, raw);
    const displayLabel = copy.metricLabel?.(key, label) ?? label;
    return formatted ? [`${displayLabel} ${formatted}`] : [];
  });
  return parts.join(" · ") || null;
}

function formatMetricValue(key: string, value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    if (key.endsWith("_pct")) return `${value.toFixed(1)}%`;
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  const text = safePreviewString(value);
  if (!text) return null;
  if (key.endsWith("_pct") && !text.includes("%")) return `${text}%`;
  return text;
}

function breakdownPreviewText(value: unknown) {
  const direct = safePreviewString(value);
  if (direct) return direct;
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const breakdown = value as Record<string, unknown>;
  const parts = [
    safePreviewString(breakdown.summary),
    safePreviewString(breakdown.what_this_means),
    safePreviewString(breakdown.what_it_means),
    safePreviewStringList(breakdown.sections).join(" · ") || null,
  ].filter((part): part is string => Boolean(part));
  return parts.join(" · ") || null;
}
