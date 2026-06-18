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

export function replaceOrAppendFinalAssistantMessage(
  messages: Message[],
  assistantId: string,
  finalAssistant: Message,
): Message[] {
  let replaced = false;
  const finalAssistantId = finalAssistant.id;
  const replacedMessages = messages.map((message) => {
    if (message.id !== assistantId && message.id !== finalAssistantId) {
      return message;
    }
    replaced = true;
    return finalAssistant;
  });

  if (replaced) {
    return replacedMessages;
  }

  return [...replacedMessages, finalAssistant];
}
