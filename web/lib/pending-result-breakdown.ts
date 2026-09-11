import type { Message } from "@/components/chat/types";
import type { ApiMessage } from "./argus-api";
import { recordOrNull, stringOrNull } from "./chat-message-hydration";

/** The saved request owns progress until its assistant message is committed. */
export function projectPendingBreakdowns(items: ApiMessage[], messages: Message[]): Message[] {
  const terminalTurns = new Set(items.flatMap((item) => {
    const turn = recordOrNull(item.metadata?.agent_runtime_turn);
    return item.role === "assistant" && turn?.terminal === true ? [turn.turn_id] : [];
  }));
  const pendingByRequest = new Map<string, Message>();
  for (const item of items) {
    const action = recordOrNull(item.metadata?.chat_action);
    const turn = recordOrNull(item.metadata?.agent_runtime_turn);
    const requestId = stringOrNull(turn?.request_id);
    if (item.role !== "user" || action?.type !== "show_breakdown" ||
      turn?.turn_id !== item.id || turn.terminal !== false || !requestId || terminalTurns.has(item.id) ||
      !["accepted", "running"].includes(String(turn.status))) continue;
    pendingByRequest.set(item.id, {
      id: `pending-breakdown:${item.id}`, role: "ai", kind: "text", content: "",
      contentPresentation: "result_breakdown",
      pendingBreakdown: { turnId: item.id, requestId, conversationId: item.conversation_id },
    });
  }
  return messages.flatMap((message) => {
    const pending = pendingByRequest.get(message.id);
    return pending ? [message, pending] : [message];
  });
}

export function retirePendingBreakdown(messages: Message[], requestId: string): Message[] {
  return messages.filter((message) => message.pendingBreakdown?.requestId !== requestId);
}
