import type { ChatActionOption } from "@/components/chat/types";
import type { DecisionState } from "@/lib/run-dossier-contract";

export type GuestConversionReason =
  | "simulation_limit"
  | "save_decision"
  | "share_result"
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
      decisionState: DecisionState | null;
      note: string;
    };

export type GuestDossierDecisionResumeTarget = Extract<
  GuestDecisionResumeTarget,
  { surface: "omnisearch_dossier" }
>;

export function dossierDecisionResumeTarget(
  target: GuestDecisionResumeTarget | null | undefined,
): GuestDossierDecisionResumeTarget | null {
  return target?.surface === "omnisearch_dossier" ? target : null;
}

type GuestPendingActionBase = {
  reason: GuestConversionReason;
  conversationId: string;
  actionId: string;
};

export type GuestPendingAction =
  | (GuestPendingActionBase & { reason: "share_result"; messageId: string })
  | (GuestPendingActionBase & {
      reason: "simulation_limit";
      action: ChatActionOption;
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
  message_id?: string;
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
    ...(action.reason === "share_result" ? { message_id: action.messageId } : {}),
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

type GuestClaim = {
  conversation_id: string;
  pending_action: {
    reason: string;
    conversation_id: string;
    action_id: string;
    message_id?: string;
  } | null;
};

export function verifiedClaimAction(
  claimed: GuestClaim,
  conversationId: string,
  latch: SingleUseGuestAction | null,
) {
  if (claimed.conversation_id !== conversationId) {
    throw new Error("The temporary conversation could not be verified.");
  }
  const expected = latch?.take() ?? null;
  if (!expected) return null;
  const claimedAction = claimed.pending_action;
  if (
    !claimedAction ||
    claimedAction.action_id !== expected.actionId ||
    claimedAction.conversation_id !== expected.conversationId ||
    claimedAction.reason !== expected.reason ||
    (expected.reason === "share_result" && claimedAction.message_id !== expected.messageId)
  ) {
    throw new Error("The pending action could not be verified.");
  }
  return expected;
}
