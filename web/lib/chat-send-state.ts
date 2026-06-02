import type { Message } from "@/components/chat/types";

type PendingAssistantMessageOptions = {
  assistantId: string;
  pendingAssistant: Message;
  userMessage: Message;
  renderUserMessage: boolean;
};

export function appendOrReplacePendingAssistantMessage(
  messages: Message[],
  {
    assistantId,
    pendingAssistant,
    userMessage,
    renderUserMessage,
  }: PendingAssistantMessageOptions,
): Message[] {
  const pending = { ...pendingAssistant, id: assistantId };
  let replaced = false;
  const replacedMessages = messages.map((message) => {
    if (message.id !== assistantId) {
      return message;
    }
    replaced = true;
    return pending;
  });

  if (replaced) {
    return replacedMessages;
  }

  return [
    ...replacedMessages,
    ...(renderUserMessage ? [userMessage] : []),
    pending,
  ];
}
