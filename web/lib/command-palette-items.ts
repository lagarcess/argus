import type {
  DecisionState,
  HistoryItem,
  SearchAssetRollupItem,
  SearchConversationItem,
  SearchLedgerGroup,
} from "./argus-api";
import type { SearchDossierAction } from "./run-dossier-contract";
import type { ConversationPreview } from "./conversation-preview-display";
import {
  commandPaletteRowActionForEvent,
  quickJumpIndexForEvent,
} from "./keyboard-shortcuts";

export type CommandPaletteDisplayItem = {
  id: string;
  type: "chat" | "conversation";
  conversationId: string | null;
  title: string;
  snippet: string;
  preview?: ConversationPreview | null;
  matchCount: number;
  matchMessageId: string | null;
  updatedAt: string;
  source: "recent" | "search";
  decisionState: DecisionState | null;
  decisionStates: DecisionState[];
  dossier: SearchConversationItem["dossier"] | null;
  totalRuns: number;
  decidedRuns: number;
  canManageConversation: boolean;
  activation: "open_conversation";
};

export type CommandPaletteLedgerDisplayGroup = {
  id: string;
  decisionState: string;
  count: number;
  items: CommandPaletteDisplayItem[];
};

export type CommandPaletteAssetRollupCopy = {
  heading?: string;
  scope?: string;
  runsInvolving?: (count: number, symbol: string) => string;
  decisionStateLabel?: (state: DecisionState) => string;
  dateLabel?: (value: string) => string;
  lastTouched?: (date: string) => string;
};

export type CommandPaletteAssetRollup = {
  heading: string;
  scope: string;
  symbol: string;
  runs: string;
  decisions: Array<{
    state: DecisionState;
    count: number;
    label: string;
  }>;
  lastTouched: string;
};

const ASSET_ROLLUP_DECISION_ORDER: readonly DecisionState[] = [
  "promising",
  "watching",
  "rejected",
  "revisit_later",
];

export function commandPaletteCanonicalRecallLimit(
  query: string,
  isLedgerMode: boolean,
): 30 | 100 {
  return isLedgerMode || query.trim() === "" ? 100 : 30;
}

export function commandPaletteItemFromHistory(
  item: HistoryItem,
): CommandPaletteDisplayItem | null {
  if (item.type !== "chat") return null;
  return {
    id: item.id,
    type: "chat",
    conversationId: item.conversation_id ?? item.id,
    title: item.title,
    snippet: "",
    preview: item.preview,
    matchCount: 1,
    matchMessageId: null,
    updatedAt: item.created_at,
    source: "recent",
    decisionState: null,
    decisionStates: [],
    dossier: null,
    totalRuns: 0,
    decidedRuns: 0,
    canManageConversation: true,
    activation: "open_conversation",
  };
}

export function commandPaletteItemsFromHistory(
  items: readonly HistoryItem[],
  recallItems: readonly SearchConversationItem[],
): CommandPaletteDisplayItem[] {
  const recallByConversationId = new Map(
    recallItems.map((item) => [item.conversation_id, item]),
  );
  const displayItems: CommandPaletteDisplayItem[] = [];

  for (const item of items) {
    const recent = commandPaletteItemFromHistory(item);
    if (!recent) continue;
    const recall = recent.conversationId
      ? recallByConversationId.get(recent.conversationId)
      : null;
    displayItems.push(
      recall
        ? {
            ...recent,
            decisionState: recall.dossier?.decision?.state ?? null,
            decisionStates: recall.decision_states,
            dossier: recall.dossier,
            totalRuns: recall.total_runs,
            decidedRuns: recall.decided_runs,
          }
        : recent,
    );
  }

  return displayItems;
}

export function commandPaletteItemFromSearch(
  item: SearchConversationItem,
): CommandPaletteDisplayItem {
  return {
    id: item.id,
    type: "conversation",
    conversationId: item.conversation_id,
    title: item.title,
    snippet: item.match.layer === "message" ? item.match.fragment : "",
    preview: item.preview,
    matchCount: item.match.count,
    matchMessageId: item.match.message_id ?? null,
    updatedAt: item.updated_at,
    source: "search",
    decisionState: item.dossier?.decision?.state ?? null,
    decisionStates: item.decision_states,
    dossier: item.dossier,
    totalRuns: item.total_runs,
    decidedRuns: item.decided_runs,
    canManageConversation: true,
    activation: "open_conversation",
  };
}

export function commandPaletteAssetRollupFromSearch(
  item: SearchAssetRollupItem,
  copy: CommandPaletteAssetRollupCopy = {},
): CommandPaletteAssetRollup {
  const date =
    copy.dateLabel?.(item.last_touched_at) ?? item.last_touched_at.slice(0, 10);
  return {
    heading: copy.heading ?? "Your Argus history",
    scope: copy.scope ?? "Across your conversations",
    symbol: item.symbol,
    runs:
      copy.runsInvolving?.(item.run_count, item.symbol) ??
      `${item.run_count} ${
        item.run_count === 1 ? "run" : "runs"
      } involving ${item.symbol}`,
    decisions: ASSET_ROLLUP_DECISION_ORDER.map((state) => {
      const count = item.decision_counts[state];
      const stateLabel =
        copy.decisionStateLabel?.(state) ??
        commandPaletteDecisionStateFallback(state);
      return {
        state,
        count,
        label: `${stateLabel} ${count}`,
      };
    }),
    lastTouched: copy.lastTouched?.(date) ?? `Last touched ${date}`,
  };
}

export function commandPaletteSelectedPreview(
  previewItem: CommandPaletteDisplayItem | null,
  displayItems: readonly CommandPaletteDisplayItem[],
): CommandPaletteDisplayItem | null {
  if (previewItem) {
    const refreshed = displayItems.find(
      (item) =>
        item.id === previewItem.id &&
        item.type === previewItem.type &&
        item.source === previewItem.source,
    );
    if (refreshed) return refreshed;
  }
  return displayItems[0] ?? null;
}

export function commandPaletteOpenMessageId(
  item: CommandPaletteDisplayItem,
  openAtLeftOff: boolean,
) {
  return openAtLeftOff ? null : item.matchMessageId;
}

export function commandPaletteConversationNavigationDisabled({
  turnInFlight,
  activeConversationId,
  targetConversationId,
}: {
  turnInFlight: boolean;
  activeConversationId: string | null;
  targetConversationId: string | null;
}) {
  return Boolean(
    turnInFlight &&
    activeConversationId &&
    targetConversationId &&
    activeConversationId === targetConversationId,
  );
}

export type CommandPaletteKeyboardAction =
  | { type: "none" }
  | { type: "select"; index: number }
  | { type: "focus_search" }
  | { type: "open"; openAtLeftOff: boolean }
  | { type: "rename" }
  | { type: "archive" }
  | { type: "delete" };

export function isEditableKeyboardTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.isContentEditable ||
    target.tagName === "INPUT" ||
    target.tagName === "TEXTAREA" ||
    target.tagName === "SELECT"
  );
}

export function commandPaletteKeyboardAction({
  key,
  itemCount,
  hasSelection,
  selectedCanManageConversation,
  targetIsEditable,
  targetIsSearchInput,
  isEditing,
  metaKey,
  ctrlKey,
  shiftKey = false,
  altKey = false,
  code = key,
  repeat = false,
  focusedRowIndex = -1,
  usesCommandKey = false,
}: {
  key: string;
  itemCount: number;
  hasSelection: boolean;
  selectedCanManageConversation?: boolean;
  targetIsEditable: boolean;
  targetIsSearchInput: boolean;
  isEditing: boolean;
  metaKey: boolean;
  ctrlKey: boolean;
  shiftKey?: boolean;
  altKey?: boolean;
  code?: string;
  repeat?: boolean;
  focusedRowIndex?: number;
  usesCommandKey?: boolean;
}): CommandPaletteKeyboardAction {
  if (isEditing || (targetIsEditable && !targetIsSearchInput)) {
    return { type: "none" };
  }
  if (key === "ArrowDown" && itemCount > 0) {
    if (targetIsSearchInput) return { type: "select", index: 0 };
    if (focusedRowIndex >= 0) {
      return {
        type: "select",
        index: Math.min(focusedRowIndex + 1, itemCount - 1),
      };
    }
  }
  if (key === "ArrowUp" && focusedRowIndex >= 0) {
    return focusedRowIndex === 0
      ? { type: "focus_search" }
      : { type: "select", index: focusedRowIndex - 1 };
  }
  if (key === "Enter" && hasSelection && focusedRowIndex < 0) {
    return { type: "open", openAtLeftOff: metaKey || ctrlKey };
  }
  const rowAction = commandPaletteRowActionForEvent({
    key,
    code,
    metaKey,
    ctrlKey,
    shiftKey,
    altKey,
    repeat,
  });
  if (
    hasSelection &&
    selectedCanManageConversation &&
    (!targetIsEditable || targetIsSearchInput) &&
    rowAction
  ) {
    return { type: rowAction };
  }
  const index = quickJumpIndexForEvent(
    {
      key,
      code,
      metaKey,
      ctrlKey,
      shiftKey,
      altKey,
      repeat,
    },
    usesCommandKey,
  );
  return index === null || index >= itemCount
    ? { type: "none" }
    : { type: "select", index };
}

export function commandPaletteRequestIsCurrent({
  capturedSignature,
  capturedRequestId,
  currentSignature,
  currentRequestId,
}: {
  capturedSignature: string;
  capturedRequestId: number;
  currentSignature: string;
  currentRequestId: number;
}) {
  return (
    capturedSignature === currentSignature &&
    capturedRequestId === currentRequestId
  );
}

export function commandPaletteDecisionVerb(
  action: Extract<SearchDossierAction, { type: "decision" }>,
) {
  return action.decision_state ? "change" : "add";
}

export function commandPaletteGroupsByLedgerState(
  items: readonly CommandPaletteDisplayItem[],
  ledgerGroups: readonly SearchLedgerGroup[],
): CommandPaletteLedgerDisplayGroup[] {
  return ledgerGroups.map((group) => ({
    id: `ledger:${group.decision_state}`,
    decisionState: group.decision_state,
    count: group.count,
    items: items.filter((item) =>
      item.decisionStates.includes(group.decision_state),
    ),
  }));
}

export function commandPaletteItemsInRenderedOrder<T>(
  groups: readonly { items: readonly T[] }[],
): T[] {
  return groups.flatMap((group) => group.items);
}

export function commandPaletteSelectedRenderedPreview(
  previewItem: CommandPaletteDisplayItem | null,
  groups: readonly { items: readonly CommandPaletteDisplayItem[] }[],
): CommandPaletteDisplayItem | null {
  return commandPaletteSelectedPreview(
    previewItem,
    commandPaletteItemsInRenderedOrder(groups),
  );
}

export function commandPaletteTypeLabelKey(
  type: CommandPaletteDisplayItem["type"],
) {
  return `command_palette.type.${type}`;
}

export function commandPaletteTypeFallback(
  type: CommandPaletteDisplayItem["type"],
) {
  void type;
  return "Conversation";
}

export function commandPaletteStatusLabelKey(item: CommandPaletteDisplayItem) {
  return item.decisionState
    ? `chat.result_card.decision_states.${item.decisionState}`
    : null;
}

export function commandPaletteStatusFallback(item: CommandPaletteDisplayItem) {
  return item.decisionState
    ? commandPaletteDecisionStateFallback(item.decisionState)
    : null;
}

export function commandPaletteOpenLabelKey(item: CommandPaletteDisplayItem) {
  void item;
  return "command_palette.open_conversation";
}

export function commandPaletteOpenFallback(item: CommandPaletteDisplayItem) {
  void item;
  return "Open conversation";
}

export function commandPaletteSupportsSearchType(type: string) {
  return type === "conversation";
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
