import type { HistoryItem, SearchItem } from "./argus-api";

export type CommandPaletteDisplayItem = {
  id: string;
  type: SearchItem["type"];
  conversationId: string | null;
  title: string;
  snippet: string;
  updatedAt: string;
  source: "recent" | "search";
  lifecycle?: string | null;
  preview?: Record<string, unknown> | null;
  canManageConversation: boolean;
  activation: "open_conversation" | "select_preview";
};

export type CommandPaletteItemCopy = {
  decisionStateLabel?: (state: string) => string;
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
    preview: safeCommandPalettePreview(item.preview),
    canManageConversation: item.type === "chat" && Boolean(conversationId),
    activation: item.type === "chat" ? "open_conversation" : "select_preview",
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
