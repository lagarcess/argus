import type {
  ChatActionOption,
  ChatMention,
} from "@/components/chat/types";
import type { DecisionState } from "@/lib/run-dossier-contract";

export type GuestConversionReason =
  | "second_simulation"
  | "message_limit"
  | "save_decision"
  | "new_conversation"
  | "keep_history"
  | "discovery_searches";

export type GuestConversionMode = "login" | "signup";

export type GuestDecisionResumeTarget =
  | {
      surface: "result_card";
      artifactId: string;
    }
  | {
      surface: "omnisearch_dossier";
      artifactId: string;
      runId: string;
      decisionState: DecisionState;
      note: string;
    };

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
      target: GuestDecisionResumeTarget;
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

export function guestConversionBenefitKey(
  reason: GuestConversionReason,
  mode: GuestConversionMode = "login",
) {
  if (reason === "new_conversation" && mode === "signup") {
    return "guest.conversion.new_conversation_create" as const;
  }
  return `guest.conversion.${reason}` as const;
}

export function newConversationConversionMode(
  publicAccountAccessEnabled: boolean,
): GuestConversionMode {
  return publicAccountAccessEnabled ? "signup" : "login";
}

export function pendingGuestActionSummary(
  action: GuestPendingAction,
): GuestPendingActionSummary {
  return {
    reason: action.reason,
    conversation_id: action.conversationId,
    action_id: action.actionId,
    ...(action.reason === "save_decision"
      ? { artifact_id: action.target.artifactId }
      : {}),
  };
}

type DecisionResumeMessage = {
  id: string;
  kind?: string;
  result?: {
    evidenceArtifactId?: string | null;
  } | null;
};

export function latestDecisionResumeMessageId(
  messages: readonly DecisionResumeMessage[],
  artifactId: string | null,
): string | null {
  if (!artifactId) return null;
  return (
    messages.findLast(
      (message) =>
        message.kind === "strategy_result" &&
        message.result?.evidenceArtifactId === artifactId,
    )?.id ?? null
  );
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
