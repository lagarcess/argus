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

export function shouldApplyConversationScopedUpdate({
  targetConversationId,
  activeConversationId,
  currentView,
  routeState,
}: {
  targetConversationId: string | null | undefined;
  activeConversationId: string | null | undefined;
  currentView: string;
  routeState: ActiveConversationRouteState;
}) {
  const target = targetConversationId?.trim();
  if (
    !shouldApplyConversationOwnedUpdate({
      targetConversationId: target,
      activeConversationId,
    })
  ) {
    return false;
  }
  return (
    currentView === "chat" &&
    routeState.isChatRoute &&
    routeState.conversationId?.trim() === target
  );
}

export function shouldApplyConversationOwnedUpdate({
  targetConversationId,
  activeConversationId,
}: {
  targetConversationId: string | null | undefined;
  activeConversationId: string | null | undefined;
}) {
  const target = targetConversationId?.trim();
  return Boolean(target && activeConversationId?.trim() === target);
}

export function shouldRetireActiveStreamForNavigation({
  activeStreamConversationId,
  nextConversationId,
}: {
  activeStreamConversationId: string | null | undefined;
  nextConversationId: string | null | undefined;
}) {
  const activeStream = activeStreamConversationId?.trim();
  if (!activeStream) return false;
  return activeStream !== (nextConversationId?.trim() ?? "");
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
