import {
  getConversationMessages,
  type ApiMessage,
  type ConversationResultCard,
} from "./argus-api";
import {
  failedActionRetryActionFromMetadata,
  isRetryAction,
  retryLastTurnActionFromMessage,
  retryLastTurnActionFromMetadata,
} from "./chat-retry-actions";
import {
  coverageRecoveryActionsFromMetadata,
  noProgressActionsFromMetadata,
  recoveryDisplayFromMetadata,
  retryableAssistantRecoveryCode,
  unsupportedStrategyActionsFromMetadata,
  unsupportedTimeframeActionsFromMetadata,
} from "./chat-recovery-display";
import { resultFactHeadingKeyFromMetadata } from "./result-followup-heading";
import type { ChatActionOption, Message } from "@/components/chat/types";

type TextMessageHydrationOptions = {
  contentPresentation?: Message["contentPresentation"];
  retryRequestMessage?: ApiMessage | null;
};

export type OrdinaryTransportAmbiguityResolution =
  | { kind: "terminal"; items: ApiMessage[] }
  | { kind: "checking"; items: ApiMessage[] }
  | { kind: "exhausted"; items: ApiMessage[] }
  | { kind: "cancelled"; items: ApiMessage[] }
  | { kind: "unknown"; items: ApiMessage[] }
  | { kind: "load_failed"; items: [] };

type HydratedMessages = {
  messages: Message[];
  inputActions: ChatActionOption[];
};

type OrdinaryTransportAmbiguityView = {
  messages: Message[] | ((current: Message[]) => Message[]);
  inputActions: ChatActionOption[];
  showChecking: boolean;
};

type OrdinaryTransportAmbiguityOptions = {
  followUpDelayMs?: number;
  followUpDelaysMs?: readonly number[];
  signal?: AbortSignal;
  wait?: (delayMs: number, signal?: AbortSignal) => Promise<void>;
};

const ORDINARY_TRANSPORT_FOLLOW_UP_DELAYS_MS = [
  250,
  1_000,
  4_000,
  15_000,
  40_000,
  60_000,
  120_000,
  240_000,
  // Final read: 900.25s, just beyond the backend's 15-minute stale reconciliation.
  420_000,
] as const;

function waitForOrdinaryTransportFollowUp(
  delayMs: number,
  signal?: AbortSignal,
): Promise<void> {
  return new Promise<void>((resolve) => {
    if (signal?.aborted) {
      resolve();
      return;
    }
    const finish = () => {
      globalThis.clearTimeout(timerId);
      signal?.removeEventListener("abort", finish);
      resolve();
    };
    const timerId = globalThis.setTimeout(finish, delayMs);
    signal?.addEventListener("abort", finish, { once: true });
  });
}

function classifyOrdinaryTransportAmbiguity(
  items: ApiMessage[],
  existingMessageIds: ReadonlySet<string> | null,
  expectedRequestId: string | null,
): OrdinaryTransportAmbiguityResolution {
  if (existingMessageIds === null || expectedRequestId === null) {
    return { kind: "unknown", items };
  }
  const newMessageIds = new Set(
    items
      .filter((message) => !existingMessageIds.has(message.id))
      .map((message) => message.id),
  );
  const lifecycleByTurnId = new Map<string, Set<string>>();
  for (const message of items) {
    if (!newMessageIds.has(message.id)) continue;
    const turn = recordOrNull(message.metadata?.agent_runtime_turn);
    const turnId = stringOrNull(turn?.turn_id);
    const requestId = stringOrNull(turn?.request_id);
    const status = stringOrNull(turn?.status);
    if (
      !turnId ||
      requestId !== expectedRequestId ||
      !status ||
      !newMessageIds.has(turnId)
    ) {
      continue;
    }
    const statuses = lifecycleByTurnId.get(turnId) ?? new Set<string>();
    statuses.add(status);
    lifecycleByTurnId.set(turnId, statuses);
  }
  if (lifecycleByTurnId.size !== 1) {
    return { kind: "unknown", items };
  }
  const statuses = [...lifecycleByTurnId.values()][0];
  if (
    [...statuses].some((status) =>
      ["completed", "recoverable_failed", "abandoned", "reconciled"].includes(
        status,
      ),
    )
  ) {
    return { kind: "terminal", items };
  }
  if ([...statuses].some((status) => ["accepted", "running"].includes(status))) {
    return { kind: "checking", items };
  }
  return { kind: "unknown", items };
}

export async function loadAllConversationMessagePages(
  conversationId: string,
  loadPage: typeof getConversationMessages = getConversationMessages,
  options: Readonly<{
    signal?: AbortSignal;
    anchorMessageId?: string;
  }> = {},
): Promise<ApiMessage[]> {
  const items: ApiMessage[] = [];
  const seenCursors = new Set<string>();
  let cursor: string | undefined;
  while (true) {
    const page = await loadPage(
      conversationId,
      100,
      cursor,
      cursor
        ? { signal: options.signal }
        : {
            signal: options.signal,
            anchorMessageId: options.anchorMessageId,
          },
    );
    items.push(...page.items);
    const nextCursor = page.next_cursor?.trim();
    if (!nextCursor) return items;
    if (seenCursors.has(nextCursor)) {
      throw new Error("Conversation message pagination repeated a cursor.");
    }
    seenCursors.add(nextCursor);
    cursor = nextCursor;
  }
}

export async function resolveOrdinaryTransportAmbiguity(
  loadMessages: () => Promise<ApiMessage[]>,
  existingMessageIds: ReadonlySet<string> | null,
  expectedRequestId: string | null,
  options: OrdinaryTransportAmbiguityOptions = {},
): Promise<OrdinaryTransportAmbiguityResolution> {
  let items: ApiMessage[];
  try {
    items = await loadMessages();
  } catch {
    return { kind: "load_failed", items: [] };
  }

  const initial = classifyOrdinaryTransportAmbiguity(
    items,
    existingMessageIds,
    expectedRequestId,
  );
  if (initial.kind !== "checking") {
    return initial;
  }

  const delays =
    options.followUpDelaysMs ??
    (options.followUpDelayMs === undefined
      ? ORDINARY_TRANSPORT_FOLLOW_UP_DELAYS_MS
      : [options.followUpDelayMs]);
  const wait = options.wait ?? waitForOrdinaryTransportFollowUp;
  let latest = initial;
  for (const delayMs of delays) {
    if (options.signal?.aborted) {
      return { kind: "cancelled", items: latest.items };
    }
    await wait(delayMs, options.signal);
    if (options.signal?.aborted) {
      return { kind: "cancelled", items: latest.items };
    }
    try {
      const followUp = classifyOrdinaryTransportAmbiguity(
        await loadMessages(),
        existingMessageIds,
        expectedRequestId,
      );
      if (followUp.kind === "terminal") return followUp;
      if (followUp.kind === "checking") latest = followUp;
    } catch {
      // A later owner-scoped read can still recover durable terminal truth.
    }
  }
  return { kind: "exhausted", items: latest.items };
}

export async function snapshotOrdinaryTransportMessageIds(
  loadMessages: () => Promise<ApiMessage[]>,
): Promise<ReadonlySet<string> | null> {
  try {
    return new Set((await loadMessages()).map((message) => message.id));
  } catch {
    return null;
  }
}

export async function resolveOrdinaryTransportAmbiguityView(
  loadMessages: () => Promise<ApiMessage[]>,
  hydrateMessages: (items: ApiMessage[]) => HydratedMessages,
  fallback: { assistantId: string; message: Message },
  existingMessageIds: ReadonlySet<string> | null,
  expectedRequestId: string | null,
  options: OrdinaryTransportAmbiguityOptions = {},
): Promise<OrdinaryTransportAmbiguityView> {
  const resolution = await resolveOrdinaryTransportAmbiguity(
    loadMessages,
    existingMessageIds,
    expectedRequestId,
    options,
  );
  if (resolution.kind === "cancelled") {
    return {
      messages: (current) => current,
      inputActions: [],
      showChecking: true,
    };
  }
  if (resolution.kind !== "terminal") {
    return {
      messages: (current) => [
        ...current.filter((message) => message.id !== fallback.assistantId),
        fallback.message,
      ],
      inputActions: [],
      showChecking: false,
    };
  }
  const hydrated = hydrateMessages(resolution.items);
  return {
    ...hydrated,
    showChecking: false,
  };
}

function retryActionsFromMetadata(
  metadata: Record<string, unknown>,
  message: ApiMessage,
  retryRequestMessage?: ApiMessage | null,
): ChatActionOption[] {
  return [
    message.role === "user"
      ? null
      : failedActionRetryActionFromMetadata(metadata),
    retryLastTurnActionFromMetadata(metadata, {
      assistantMessageId: message.role === "user" ? undefined : message.id,
      owningMessageId: message.id,
      persistedMessage: retryRequestMessage?.content ?? message.content,
      messageRole: message.role === "user" ? "user" : "assistant",
      requestMessageId: retryRequestMessage?.id,
    }),
  ].filter((action): action is ChatActionOption => Boolean(action));
}

export function precedingUserMessageForRetryableRecovery(
  messages: ApiMessage[],
  assistant: ApiMessage,
): ApiMessage | null {
  if (assistant.role === "user") return null;
  if (!retryableAssistantRecoveryCode((assistant.metadata ?? {}).recovery)) {
    return null;
  }
  const index = messages.findIndex((message) => message.id === assistant.id);
  for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
    const candidate = messages[cursor];
    if (candidate.role === "user") {
      return (candidate.content ?? "").trim() ? candidate : null;
    }
  }
  return null;
}

export function retryRequestMessageForAssistant(
  messages: ApiMessage[],
  assistant: ApiMessage,
): ApiMessage | null {
  if (assistant.role === "user") return null;
  const metadata = assistant.metadata ?? {};
  const retry = recordOrNull(metadata.retry_last_turn);
  const turn = recordOrNull(metadata.agent_runtime_turn);
  const requestMessageId = stringOrNull(retry?.request_message_id)?.trim();
  if (
    !requestMessageId ||
    stringOrNull(turn?.turn_id)?.trim() !== requestMessageId
  ) {
    return null;
  }
  return (
    messages.find(
      (message) =>
        message.id === requestMessageId && message.role === "user",
    ) ?? null
  );
}

export function stringOrNull(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

export function recordOrNull(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function stringArrayOrNull(value: unknown): string[] | null {
  if (!Array.isArray(value)) {
    return null;
  }
  const values = value.map(String).filter(Boolean);
  return values.length > 0 ? values : null;
}

export function isHydratableResultCard(
  value: unknown,
): value is ConversationResultCard {
  const card = recordOrNull(value);
  const dateRange = recordOrNull(card?.date_range);
  return Boolean(
    card &&
      typeof card.title === "string" &&
      typeof card.status_label === "string" &&
      Array.isArray(card.rows) &&
      Array.isArray(card.assumptions) &&
      Array.isArray(card.actions) &&
      dateRange &&
      typeof dateRange.start === "string" &&
      typeof dateRange.end === "string" &&
      typeof dateRange.display === "string",
  );
}

export function hydrateTextMessageFromApi(
  message: ApiMessage,
  options: TextMessageHydrationOptions = {},
): Message {
  const metadata = message.metadata ?? {};
  const isAssistant = message.role !== "user";
  const retryActions = retryActionsFromMetadata(
    metadata,
    message,
    options.retryRequestMessage,
  );
  const coverageActions = isAssistant
    ? coverageRecoveryActionsFromMetadata(metadata, message.id)
    : [];
  const noProgressActions = isAssistant
    ? noProgressActionsFromMetadata(metadata, message.id)
    : [];
  const unsupportedTimeframeActions = isAssistant
    ? unsupportedTimeframeActionsFromMetadata(metadata, message.id)
    : [];
  const unsupportedStrategyActions = isAssistant
    ? unsupportedStrategyActionsFromMetadata(metadata, message.id)
    : [];
  const actions = [
    ...coverageActions,
    ...noProgressActions,
    ...unsupportedTimeframeActions,
    ...unsupportedStrategyActions,
    ...retryActions,
  ];
  // A retryable composition failure resolves in place: one tap re-sends
  // the original turn and the replaced failure is superseded durably.
  const compositionRecoveryCode = isAssistant
    ? retryableAssistantRecoveryCode(metadata.recovery)
    : null;
  if (
    compositionRecoveryCode &&
    options.retryRequestMessage &&
    !actions.some(isRetryAction)
  ) {
    const compositionRetry = retryLastTurnActionFromMessage(
      options.retryRequestMessage.content ?? "",
      {
        assistantMessageId: message.id,
        requestMessageId: options.retryRequestMessage.id,
      },
    );
    if (compositionRetry) actions.push(compositionRetry);
  }

  return {
    id: message.id,
    role: message.role === "user" ? "user" : "ai",
    kind: "text",
    content: message.content,
    actions: actions.length > 0 ? actions : undefined,
    contentPresentation: isAssistant
      ? runtimeFailureContentPresentation(metadata, options.contentPresentation)
      : undefined,
    resultFactHeadingKey: isAssistant
      ? resultFactHeadingKeyFromMetadata(metadata)
      : undefined,
    recoveryDisplay: recoveryDisplayFromMetadata(metadata),
    assistantRecoveryCode: isAssistant
      ? retryableAssistantRecoveryCode(metadata.recovery)
      : null,
  };
}

function runtimeFailureContentPresentation(
  metadata: Record<string, unknown>,
  fallback: Message["contentPresentation"],
): Message["contentPresentation"] {
  if (metadata.agent_runtime_failure_superseded === true) {
    return "superseded_runtime_failure";
  }
  return fallback;
}
