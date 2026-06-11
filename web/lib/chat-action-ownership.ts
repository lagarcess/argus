import type { ChatActionOption } from "@/components/chat/types";

const CARD_SCOPED_ACTION_TYPES = new Set<NonNullable<ChatActionOption["type"]>>([
  "run_backtest",
  "change_dates",
  "change_asset",
  "adjust_assumptions",
  "cancel_confirmation",
  "show_breakdown",
  "refine_strategy",
  "save_strategy",
]);

const CONFIRMATION_ACTION_TYPES = new Set<NonNullable<ChatActionOption["type"]>>([
  "run_backtest",
  "change_dates",
  "change_asset",
  "adjust_assumptions",
  "cancel_confirmation",
]);

export function isCardScopedAction(action: ChatActionOption) {
  return Boolean(action.type && CARD_SCOPED_ACTION_TYPES.has(action.type));
}

export function isConfirmationAction(action: ChatActionOption | undefined) {
  return Boolean(action?.type && CONFIRMATION_ACTION_TYPES.has(action.type));
}

export function actionHasCardScopedOwnership(action: ChatActionOption) {
  return (
    isCardScopedAction(action) ||
    action.presentation === "confirmation" ||
    action.presentation === "result"
  );
}

export function visibleInputActions(actions: ChatActionOption[]) {
  return actions.filter((action) => action.type !== "save_strategy");
}

export function visibleComposerActions(actions: ChatActionOption[]) {
  return visibleInputActions(actions).filter(
    (action) => !actionHasCardScopedOwnership(action),
  );
}
