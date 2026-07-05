import type { ChatActionOption, Message } from "@/components/chat/types";

type MergeFinalTextOptions = {
  assistantId: string;
  finalText: string;
  finalActions: ChatActionOption[];
  contentPresentation?: Message["contentPresentation"];
  resultFactHeadingKey?: string | null;
};

export function mergeFinalTextMessage(
  message: Message,
  {
    assistantId,
    finalText,
    finalActions,
    contentPresentation,
    resultFactHeadingKey,
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
  };
}
