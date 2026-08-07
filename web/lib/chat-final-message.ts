import type {
  ChatActionOption,
  DiscoverySidecar,
  Message,
} from "@/components/chat/types";
import type { NextExperimentRow } from "./chat-next-experiments";
import type { RecoveryDisplay } from "./chat-recovery-display";
import type { MemoryRecallItem } from "./memory-recalls";

type MergeFinalTextOptions = {
  assistantId: string;
  finalText: string;
  finalActions: ChatActionOption[];
  contentPresentation?: Message["contentPresentation"];
  resultFactHeadingKey?: string | null;
  recoveryDisplay?: RecoveryDisplay | null;
  strategyPathContext?: Message["strategyPathContext"];
  assistantRecoveryCode?: string | null;
  discovery?: DiscoverySidecar | null;
  memoryRecalls?: MemoryRecallItem[] | null;
  nextExperiments?: NextExperimentRow[] | null;
};

export function mergeFinalTextMessage(
  message: Message,
  {
    assistantId,
    finalText,
    finalActions,
    contentPresentation,
    resultFactHeadingKey,
    recoveryDisplay,
    strategyPathContext,
    assistantRecoveryCode,
    discovery,
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
    actions: finalActions.length > 0 ? finalActions : message.actions,
    contentPresentation: contentPresentation ?? message.contentPresentation,
    resultFactHeadingKey: resultFactHeadingKey ?? message.resultFactHeadingKey,
    recoveryDisplay: recoveryDisplay ?? message.recoveryDisplay,
    strategyPathContext:
      strategyPathContext ?? message.strategyPathContext,
    assistantRecoveryCode: assistantRecoveryCode ?? message.assistantRecoveryCode,
    discovery: discovery ?? message.discovery,
    memoryRecalls: memoryRecalls ?? message.memoryRecalls,
    nextExperiments: nextExperiments ?? message.nextExperiments,
  };
}
