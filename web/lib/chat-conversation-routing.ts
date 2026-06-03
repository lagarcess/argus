import type { ChatActionOption } from "@/components/chat/types";

export type ActiveConversationRouteState = {
  conversationId: string | null;
  isChatRoute: boolean;
  isNewChatRoute: boolean;
};

export function activeConversationRouteStateFromUrl(
  href: string,
  queryKey = "conversation",
): ActiveConversationRouteState {
  try {
    const url = new URL(href);
    const conversationId = url.searchParams.get(queryKey)?.trim() || null;
    const isChatRoute = url.pathname === "/chat";
    return {
      conversationId: isChatRoute ? conversationId : null,
      isChatRoute,
      isNewChatRoute: isChatRoute && conversationId === null,
    };
  } catch {
    return {
      conversationId: null,
      isChatRoute: false,
      isNewChatRoute: false,
    };
  }
}

export function shouldStartConversationForVisibleEmptyChat({
  routeState,
  visibleMessageCount,
  hasStructuredAction,
}: {
  routeState: ActiveConversationRouteState;
  visibleMessageCount: number;
  hasStructuredAction: boolean;
}) {
  return (
    routeState.isNewChatRoute &&
    visibleMessageCount === 0 &&
    !hasStructuredAction
  );
}

export function actionConversationId(action: ChatActionOption | null | undefined) {
  const rawConversationId =
    action?.payload?.conversation_id ?? action?.payload?.conversationId;
  if (typeof rawConversationId !== "string") return null;
  return rawConversationId.trim() || null;
}

export function targetConversationIdForSend({
  routeConversationId,
  stateConversationId,
  action,
}: {
  routeConversationId: string | null | undefined;
  stateConversationId: string | null | undefined;
  action: ChatActionOption | null | undefined;
}) {
  return (
    actionConversationId(action) ??
    routeConversationId?.trim() ??
    stateConversationId?.trim() ??
    null
  );
}
