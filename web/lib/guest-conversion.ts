import type {
  ChatActionOption,
  ChatMention,
} from "@/components/chat/types";

export type GuestConversionReason =
  | "second_simulation"
  | "message_limit"
  | "save_decision"
  | "new_conversation"
  | "keep_history";

type GuestPendingActionBase = {
  reason: GuestConversionReason;
  conversationId: string;
  actionId: string;
};

export type GuestPendingAction =
  | (GuestPendingActionBase & {
      reason: "second_simulation";
      action: ChatActionOption;
    })
  | (GuestPendingActionBase & {
      reason: "message_limit";
      text: string;
      mentions: ChatMention[];
    })
  | (GuestPendingActionBase & {
      reason: "save_decision";
      artifactId: string;
    })
  | (GuestPendingActionBase & {
      reason: "new_conversation" | "keep_history";
    });

export type GuestPendingActionSummary = {
  reason: GuestConversionReason;
  conversation_id: string;
  action_id: string;
  artifact_id?: string;
};

export function guestConversionBenefitKey(reason: GuestConversionReason) {
  return `guest.conversion.${reason}` as const;
}

export function pendingGuestActionSummary(
  action: GuestPendingAction,
): GuestPendingActionSummary {
  return {
    reason: action.reason,
    conversation_id: action.conversationId,
    action_id: action.actionId,
    ...("artifactId" in action ? { artifact_id: action.artifactId } : {}),
  };
}

export class SingleUseGuestAction {
  private action: GuestPendingAction | null;

  constructor(action: GuestPendingAction) {
    this.action = action;
  }

  take() {
    const action = this.action;
    this.action = null;
    return action;
  }
}
