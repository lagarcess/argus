import type {
  ChatActionOption,
  DiscoverySidecar,
  DiscoverySource,
  Message,
} from "@/components/chat/types";
import type { NextExperimentRow } from "./chat-next-experiments";
import type { RecoveryDisplay } from "./chat-recovery-display";
import type { MemoryRecallItem } from "./memory-recalls";

type MergeFinalTextOptions = {
  assistantId: string;
  finalText: string;
  resultReadoutContent?: Message["resultReadoutContent"];
  resultReadoutFacts?: Message["resultReadoutFacts"];
  toolResultCards?: Message["toolResultCards"];
  finalActions: ChatActionOption[];
  contentPresentation?: Message["contentPresentation"];
  resultFactHeadingKey?: string | null;
  recoveryDisplay?: RecoveryDisplay | null;
  strategyPathContext?: Message["strategyPathContext"];
  assistantRecoveryCode?: string | null;
  discovery?: DiscoverySidecar | null;
  /** Typed citations for this turn; the panel's only input. */
  researchSources?: DiscoverySource[] | null;
  /** The sidecar's degraded code; frames those citations as where Argus looked. */
  researchDegradedCode?: string | null;
  memoryRecalls?: MemoryRecallItem[] | null;
  nextExperiments?: NextExperimentRow[] | null;
};

export function mergeFinalTextMessage(
  message: Message,
  {
    assistantId,
    finalText,
    resultReadoutContent,
    resultReadoutFacts,
    toolResultCards,
    finalActions,
    contentPresentation,
    resultFactHeadingKey,
    recoveryDisplay,
    strategyPathContext,
    assistantRecoveryCode,
    discovery,
    researchSources,
    researchDegradedCode,
    memoryRecalls,
    nextExperiments,
  }: MergeFinalTextOptions,
): Message {
  if (message.id !== assistantId) {
    return message;
  }

  return {
    ...message,
    content: finalText || message.content || undefined,
    toolResultCards: toolResultCards ?? message.toolResultCards,
    actions: finalActions.length > 0 ? finalActions : message.actions,
    contentPresentation: contentPresentation ?? message.contentPresentation,
    resultReadoutContent,
    resultReadoutFacts,
    resultFactHeadingKey: resultFactHeadingKey ?? message.resultFactHeadingKey,
    recoveryDisplay: recoveryDisplay ?? message.recoveryDisplay,
    strategyPathContext:
      strategyPathContext ?? message.strategyPathContext,
    assistantRecoveryCode: assistantRecoveryCode ?? message.assistantRecoveryCode,
    discovery: discovery ?? message.discovery,
    researchSources: researchSources ?? message.researchSources,
    researchDegradedCode: researchDegradedCode ?? message.researchDegradedCode,
    memoryRecalls: memoryRecalls ?? message.memoryRecalls,
    nextExperiments: nextExperiments ?? message.nextExperiments,
  };
}
