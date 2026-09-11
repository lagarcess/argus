export type ChatFeedbackDialogState = {
  isOpen: boolean;
  type: "bug" | "feature" | "general" | "rating";
  rating?: "positive" | "negative";
  context?: Record<string, unknown>;
};

export function openFeedbackDialogState(
  type: ChatFeedbackDialogState["type"],
  context: Record<string, unknown> | undefined,
  rating: ChatFeedbackDialogState["rating"],
  conversationId: string | null,
): ChatFeedbackDialogState {
  return {
    isOpen: true,
    type,
    context: { ...context, conversation_id: conversationId },
    rating,
  };
}
