import type { StarterSelectionMetadata } from "@/components/chat/StarterActions";
import type { ChatActionOption, ChatMention } from "./types";

export type SendOptions = {
  renderUserMessage?: boolean;
  replacementAssistantId?: string;
  bypassGuestGate?: boolean;
};

export type SendSelection =
  | ChatMention[]
  | ChatActionOption
  | StarterSelectionMetadata;

export type GuestPendingSubmission = {
  text: string;
  mentionsOrAction?: SendSelection;
  actionArg?: ChatActionOption;
  options?: SendOptions;
};

export function isStarterSelectionMetadata(
  selection: SendSelection | undefined,
): selection is StarterSelectionMetadata {
  return (
    !Array.isArray(selection) &&
    typeof selection === "object" &&
    selection !== null &&
    "strategy_category" in selection &&
    !("type" in selection)
  );
}
