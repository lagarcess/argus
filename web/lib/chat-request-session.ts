import type { ConversationOperationKind } from "./argus-api";
import type { ConversationActivityRuntime } from "../components/chat/useConversationActivity";
import {
  shouldApplyConversationRequestUpdate,
  type ActiveConversationRouteState,
} from "./chat-conversation-routing";

type ActiveOperationKind = Exclude<ConversationOperationKind, null>;

export const visibleRequestStatus = (
  status: string | null,
  isConversationLocked: boolean,
): string | null => (isConversationLocked ? status : null);

export type ChatRequestCallbackKind =
  | "stage"
  | "token"
  | "title"
  | "final"
  | "done"
  | "error"
  | "catch"
  | "save_cleanup"
  | "cancel"
  | "run_replay"
  | "ambiguity";

export type ChatRequestSession = Readonly<{
  identity: Readonly<{
    conversationId: string;
    requestId: string;
    issuedRevision: number;
  }>;
  controller: AbortController;
  accountEpoch: number;
  kind: ActiveOperationKind;
}>;

export type ChatRequestRouteContext = Readonly<{
  activeConversationId: string | null;
  currentView: string;
  routeState: ActiveConversationRouteState;
}>;

export type ChatRequestSessionController = Readonly<{
  begin: (
    conversationId: string,
    kind: ActiveOperationKind,
  ) => ChatRequestSession | null;
  authorize: (
    session: ChatRequestSession,
    kind: ChatRequestCallbackKind,
    payloadConversationId?: string,
  ) => boolean;
  canWriteVisible: (session: ChatRequestSession) => boolean;
  isAccountCurrent: (session: ChatRequestSession) => boolean;
  finishTransport: (session: ChatRequestSession) => boolean;
  transfer: (
    session: ChatRequestSession,
    conversationId: string,
  ) => ChatRequestSession | null;
  updateRouteContext: (routeContext: ChatRequestRouteContext) => void;
  synchronizeAccountScope: (accountScopeKey: string | null) => boolean;
}>;

type ChatRequestActivityPort = Pick<
  ConversationActivityRuntime,
  | "finishTransport"
  | "isConversationLocked"
  | "isRequestCurrent"
  | "registerTransport"
  | "releaseTransport"
  | "retireRequest"
  | "startRequest"
  | "synchronizeAccountScope"
>;

export function createChatRequestSessionController(options: Readonly<{
  activity: ChatRequestActivityPort;
  accountScopeKey: string | null;
  routeContext: ChatRequestRouteContext;
  createRequestId?: () => string;
}>): ChatRequestSessionController {
  const endedTransports = new WeakSet<ChatRequestSession>();
  const activeControllers = new Set<AbortController>();
  let accountScopeKey = options.accountScopeKey;
  let accountEpoch = 0;
  let routeContext = options.routeContext;
  const createRequestId = options.createRequestId ?? (() => crypto.randomUUID());

  const isCurrent = (
    session: ChatRequestSession,
    scope: "request" | "visible",
  ): boolean => {
    if (session.accountEpoch !== accountEpoch) return false;
    return shouldApplyConversationRequestUpdate({
      targetConversationId: session.identity.conversationId,
      requestId: session.identity.requestId,
      currentRequestId: options.activity.isRequestCurrent(
        session.identity.conversationId,
        session.identity.requestId,
      )
        ? session.identity.requestId
        : null,
      scope,
      activeConversationId: routeContext.activeConversationId,
      currentView: routeContext.currentView,
      routeState: routeContext.routeState,
    });
  };

  const createSession = (
    conversationId: string,
    requestId: string,
    kind: ActiveOperationKind,
    controller: AbortController,
  ): ChatRequestSession => {
    const issuedRevision = options.activity.startRequest(
      conversationId,
      requestId,
      "queued",
      kind,
    );
    options.activity.registerTransport(conversationId, requestId, controller);
    activeControllers.add(controller);
    return {
      identity: {
        conversationId,
        requestId,
        issuedRevision,
      },
      controller,
      accountEpoch,
      kind,
    };
  };

  return {
    begin: (conversationId, kind) => {
      const target = conversationId.trim();
      if (
        !target ||
        !accountScopeKey ||
        options.activity.isConversationLocked(target)
      ) {
        return null;
      }
      return createSession(
        target,
        createRequestId(),
        kind,
        new AbortController(),
      );
    },
    authorize: (session, kind, payloadConversationId) => {
      if (
        kind === "title" &&
        payloadConversationId?.trim() !== session.identity.conversationId
      ) {
        return false;
      }
      const visibleOnly =
        kind === "token" ||
        kind === "final" ||
        kind === "save_cleanup" ||
        kind === "cancel";
      return isCurrent(session, visibleOnly ? "visible" : "request");
    },
    canWriteVisible: (session) => isCurrent(session, "visible"),
    isAccountCurrent: (session) => session.accountEpoch === accountEpoch,
    finishTransport: (session) => {
      if (endedTransports.has(session)) return false;
      endedTransports.add(session);
      activeControllers.delete(session.controller);
      return options.activity.finishTransport(
        session.identity.conversationId,
        session.identity.requestId,
        session.controller,
      );
    },
    transfer: (session, conversationId) => {
      const target = conversationId.trim();
      if (!target || !isCurrent(session, "request")) return null;
      options.activity.releaseTransport(
        session.identity.conversationId,
        session.identity.requestId,
        session.controller,
      );
      if (
        !options.activity.retireRequest(
          session.identity.conversationId,
          session.identity.requestId,
        )
      ) {
        return null;
      }
      return createSession(
        target,
        session.identity.requestId,
        session.kind,
        session.controller,
      );
    },
    updateRouteContext: (nextRouteContext) => {
      routeContext = nextRouteContext;
    },
    synchronizeAccountScope: (nextAccountScopeKey) => {
      if (nextAccountScopeKey === accountScopeKey) return false;
      accountScopeKey = nextAccountScopeKey;
      accountEpoch += 1;
      for (const controller of activeControllers) controller.abort();
      activeControllers.clear();
      options.activity.synchronizeAccountScope(nextAccountScopeKey);
      return true;
    },
  };
}
