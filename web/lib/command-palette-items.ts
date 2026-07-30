import type {
  DecisionState,
  HistoryItem,
  SearchAssetRollupItem,
  SearchConversationItem,
  SearchLedgerGroup,
} from "./argus-api";

export type CommandPaletteDisplayItem = {
  id: string;
  type: "chat" | "conversation";
  conversationId: string | null;
  title: string;
  snippet: string;
  matchCount: number;
  matchMessageId: string | null;
  updatedAt: string;
  source: "recent" | "search";
  decisionState: DecisionState | null;
  decisionStates: DecisionState[];
  dossier: SearchConversationItem["dossier"] | null;
  actions: SearchConversationItem["actions"];
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
  decisionAttribution?: (state: string, run: string) => string;
  runCountLabel?: (count: number) => string;
  strategyFamilyLabel?: (family: string) => string;
  dateLabel?: (value: string) => string;
  nudgeLabel?: (nudge: string) => string;
  metricLabel?: (id: string, fallback: string) => string;
};

export type CommandPaletteAssetRollupCopy = {
  heading?: string;
  runsInvolving?: (count: number, symbol: string) => string;
  decisionStateLabel?: (state: DecisionState) => string;
  dateLabel?: (value: string) => string;
  lastTouched?: (date: string) => string;
};

export type CommandPaletteAssetRollup = {
  heading: string;
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
    matchCount: 1,
    matchMessageId: null,
    updatedAt: item.created_at,
    source: "recent",
    decisionState: null,
    decisionStates: [],
    dossier: null,
    actions: [],
    canManageConversation: true,
    activation: "open_conversation",
  };
}

export function commandPaletteItemFromSearch(
  item: SearchConversationItem,
  copy: CommandPaletteItemCopy = {},
): CommandPaletteDisplayItem {
  void copy;
  return {
    id: item.id,
    type: "conversation",
    conversationId: item.conversation_id,
    title: item.title,
    snippet: item.matched_text,
    matchCount: item.match.count,
    matchMessageId: item.match.message_id ?? null,
    updatedAt: item.updated_at,
    source: "search",
    decisionState: item.dossier.decision?.state ?? null,
    decisionStates: item.decision_states,
    dossier: item.dossier,
    actions: item.actions,
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
    heading: copy.heading ?? "Your history with this asset",
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

export function commandPaletteDigitSelectionIndex(
  key: string,
  itemCount: number,
  isEditableTarget: boolean,
) {
  if (isEditableTarget || !/^[1-9]$/.test(key)) return null;
  const index = Number(key) - 1;
  return index < itemCount ? index : null;
}

export type CommandPaletteKeyboardAction =
  | { type: "none" }
  | { type: "select"; index: number }
  | { type: "open"; openAtLeftOff: boolean };

export function commandPaletteKeyboardAction({
  key,
  itemCount,
  hasSelection,
  targetIsEditable,
  targetIsSearchInput,
  isEditing,
  metaKey,
  ctrlKey,
}: {
  key: string;
  itemCount: number;
  hasSelection: boolean;
  targetIsEditable: boolean;
  targetIsSearchInput: boolean;
  isEditing: boolean;
  metaKey: boolean;
  ctrlKey: boolean;
}): CommandPaletteKeyboardAction {
  if (isEditing || (targetIsEditable && !targetIsSearchInput)) {
    return { type: "none" };
  }
  if (key === "Enter" && hasSelection) {
    return { type: "open", openAtLeftOff: metaKey || ctrlKey };
  }
  const index = commandPaletteDigitSelectionIndex(
    key,
    itemCount,
    targetIsEditable,
  );
  return index === null ? { type: "none" } : { type: "select", index };
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
  action: Extract<
    SearchConversationItem["actions"][number],
    { type: "decision" }
  >,
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

export function commandPalettePreviewFields(
  item: CommandPaletteDisplayItem,
  copy: CommandPaletteItemCopy = {},
): CommandPalettePreviewField[] {
  const dossier = item.dossier;
  if (!dossier) return [];
  const fields: CommandPalettePreviewField[] = [];
  const add = (id: string, fallback: string, value: string | null) => {
    if (!value) return;
    fields.push({
      id,
      labelKey: `command_palette.preview_fields.${id}`,
      labelFallback: fallback,
      value,
    });
  };

  if (dossier.decision) {
    const state =
      copy.decisionStateLabel?.(dossier.decision.state) ??
      commandPaletteDecisionStateFallback(dossier.decision.state);
    add(
      "decision",
      "Decision",
      dossier.decision.run_label
        ? (copy.decisionAttribution?.(state, dossier.decision.run_label) ??
            `${state} · on ${dossier.decision.run_label}`)
        : state,
    );
    // Do not trim or normalize: this is the user's exact stored note.
    add("note", "Your note", dossier.decision.note);
  }

  const tested = dossier.tested;
  const testedParts = [
    tested.symbols.join(", ") || null,
    tested.strategy_families
      .map(
        (family) =>
          copy.strategyFamilyLabel?.(family) ?? strategyFamilyFallback(family),
      )
      .join(", ") || null,
    copy.runCountLabel?.(tested.run_count) ??
      `${tested.run_count} ${tested.run_count === 1 ? "run" : "runs"}`,
    tested.start_date && tested.end_date
      ? `${copy.dateLabel?.(tested.start_date) ?? tested.start_date}–${
          copy.dateLabel?.(tested.end_date) ?? tested.end_date
        }`
      : tested.start_date || tested.end_date
        ? (copy.dateLabel?.(tested.start_date ?? tested.end_date ?? "") ??
          tested.start_date ??
          tested.end_date)
        : null,
  ].filter((value): value is string => Boolean(value));
  add("tested", "What you tested", testedParts.join(" · "));

  if (dossier.outcome) {
    const outcomeParts = [
      dossier.outcome.quick_take,
      metricsText(dossier.outcome.metrics, copy),
    ].filter((value): value is string => Boolean(value));
    add("outcome", "How it went", outcomeParts.join(" · "));
  }

  if (dossier.left_off) {
    add(
      "left_off",
      "Where you left off",
      [
        dossier.left_off.run_label,
        copy.dateLabel?.(dossier.left_off.completed_at) ??
          dossier.left_off.completed_at.slice(0, 10),
        dossier.left_off.nudge
          ? (copy.nudgeLabel?.(dossier.left_off.nudge) ??
            nudgeFallback(dossier.left_off.nudge))
          : null,
      ]
        .filter(Boolean)
        .join(" · "),
    );
  }
  return fields;
}

function strategyFamilyFallback(family: string) {
  const labels: Record<string, string> = {
    buy_and_hold: "Buy and hold",
    buy_hold: "Buy and hold",
    buy_the_dip: "Buy the dip",
    dca: "Recurring buys",
    dca_accumulation: "Recurring buys",
    moving_average_crossover: "Moving-average crossover",
    rsi_mean_reversion: "RSI threshold",
  };
  return labels[family] ?? "Strategy";
}

function nudgeFallback(nudge: string) {
  const labels: Record<string, string> = {
    stale_result: "Result may need a refresh",
    suggestion_untaken: "Suggested next step",
    undecided: "No decision yet",
  };
  return labels[nudge] ?? "Next step saved";
}

function metricsText(
  metrics: Array<{ name: string; value: string | number }>,
  copy: CommandPaletteItemCopy,
) {
  if (!Array.isArray(metrics)) return null;
  const labels: Record<string, string> = {
    benchmark_return_pct: "Benchmark return",
    delta_vs_benchmark_pct: "Against benchmark",
    excess_return_pct: "Against benchmark",
    max_drawdown_pct: "Worst drop",
    sharpe_ratio: "Sharpe",
    total_return_pct: "Total return",
    volatility_pct: "Volatility",
  };
  return metrics
    .map(({ name, value }) => {
      const label =
        copy.metricLabel?.(name, labels[name] ?? name) ?? labels[name] ?? name;
      const rendered =
        typeof value === "number" && name.endsWith("_pct")
          ? `${value.toFixed(1)}%`
          : String(value);
      return `${label} ${rendered}`;
    })
    .join(" · ");
}
