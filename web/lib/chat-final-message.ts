import type {
  ChatActionOption,
  DiscoverySidecar,
  Message,
} from "@/components/chat/types";
import type { RecoveryDisplay } from "./chat-recovery-display";

type MergeFinalTextOptions = {
  assistantId: string;
  finalText: string;
  finalActions: ChatActionOption[];
  contentPresentation?: Message["contentPresentation"];
  resultFactHeadingKey?: string | null;
  recoveryDisplay?: RecoveryDisplay | null;
  assistantRecoveryCode?: string | null;
  discovery?: DiscoverySidecar | null;
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
    assistantRecoveryCode,
    discovery,
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
    assistantRecoveryCode: assistantRecoveryCode ?? message.assistantRecoveryCode,
    discovery: discovery ?? message.discovery,
  };
}
