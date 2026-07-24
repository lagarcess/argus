import {
  getConversationMessages,
  type ApiMessage,
  type ConversationResultCard,
} from "./argus-api";
import {
  failedActionRetryActionFromMetadata,
  retryLastTurnActionFromMetadata,
} from "./chat-retry-actions";
import {
  coverageRecoveryActionsFromMetadata,
  recoveryDisplayFromMetadata,
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
  wait?: (delayMs: number) => Promise<void>;
};

const ORDINARY_TRANSPORT_FOLLOW_UP_DELAY_MS = 250;

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
): Promise<ApiMessage[]> {
  const items: ApiMessage[] = [];
  const seenCursors = new Set<string>();
  let cursor: string | undefined;
  while (true) {
    const page = await loadPage(conversationId, 100, cursor);
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

  const wait =
    options.wait ??
    ((delayMs: number) =>
      new Promise<void>((resolve) => {
        globalThis.setTimeout(resolve, delayMs);
      }));
  await wait(
    options.followUpDelayMs ?? ORDINARY_TRANSPORT_FOLLOW_UP_DELAY_MS,
  );
  try {
    const followUpItems = await loadMessages();
    const followUp = classifyOrdinaryTransportAmbiguity(
      followUpItems,
      existingMessageIds,
      expectedRequestId,
    );
    return followUp.kind === "unknown" ? initial : followUp;
  } catch {
    return initial;
  }
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
): Promise<OrdinaryTransportAmbiguityView> {
  const resolution = await resolveOrdinaryTransportAmbiguity(
    loadMessages,
    existingMessageIds,
    expectedRequestId,
  );
  if (resolution.kind === "load_failed") {
    return {
      messages: (current) => [
        ...current.filter((message) => message.id !== fallback.assistantId),
        fallback.message,
      ],
      inputActions: [],
      showChecking: false,
    };
  }
  if (resolution.kind !== "terminal") {
    return {
      messages: (current) => current,
      inputActions: [],
      showChecking: true,
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
  const unsupportedTimeframeActions = isAssistant
    ? unsupportedTimeframeActionsFromMetadata(metadata, message.id)
    : [];
  const actions = [
    ...coverageActions,
    ...unsupportedTimeframeActions,
    ...retryActions,
  ];

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
