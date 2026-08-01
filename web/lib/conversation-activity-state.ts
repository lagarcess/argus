import type {
  ConversationActivity,
  ConversationActivityPatch,
  ConversationOperationKind,
  ConversationOperationStatus,
  HistoryItem,
} from "./argus-api";

export type ConversationActivityCausalClock = Readonly<{
  nextRevision: () => number;
}>;

export const createConversationActivityCausalClock = (): ConversationActivityCausalClock => {
  let revision = 0;
  return {
    nextRevision: () => {
      revision += 1;
      return revision;
    },
  };
};

export type ConversationActivityHistorySnapshot = Readonly<{
  items: readonly HistoryItem[];
  revision: number;
}>;

export type ConversationActivityPresentation =
  | "working"
  | "needs_attention"
  | "needs_input"
  | "new_activity"
  | "manual_unread"
  | "none";

type ActiveOperationStatus = Exclude<ConversationOperationStatus, "idle">;

export type ConversationActivityRequestRecord = {
  requestId: string;
  status: ActiveOperationStatus;
  kind: Exclude<ConversationOperationKind, null>;
  issuedRevision: number;
  transportFinishedRevision: number | null;
};

export type ConversationActivityMutationRecord = {
  mutationId: string;
  action: ConversationActivityPatch["action"];
  issuedRevision: number;
  guardGenerationAtStart: number;
};

export type ConversationActivityAnnouncement = {
  key: string;
  presentation: Exclude<ConversationActivityPresentation, "none">;
};

export type ConversationActivityRecord = {
  canonical: ConversationActivity | null;
  serverRevision: number;
  request: ConversationActivityRequestRecord | null;
  mutation: ConversationActivityMutationRecord | null;
  manualUnreadGuardSource: "server" | string | null;
  manualUnreadGuardGeneration: number;
  announcement: ConversationActivityAnnouncement | null;
  announcementFingerprint: string;
  announcementGeneration: number;
  acknowledgedAnnouncements: Readonly<Record<string, true>>;
};

export type ConversationActivityState = {
  byConversationId: Readonly<Record<string, ConversationActivityRecord>>;
};

export type ConversationActivityAction =
  | {
      type: "server_projection_merged";
      conversationId: string;
      activity: ConversationActivity;
      revision: number;
      activeView?: boolean;
    }
  | {
      type: "request_started";
      conversationId: string;
      requestId: string;
      status: ActiveOperationStatus;
      kind: Exclude<ConversationOperationKind, null>;
      revision: number;
    }
  | {
      type: "request_progressed";
      conversationId: string;
      requestId: string;
      status: ActiveOperationStatus;
    }
  | {
      type: "request_transport_finished";
      conversationId: string;
      requestId: string;
      revision: number;
    }
  | {
      type: "request_retired";
      conversationId: string;
      requestId: string;
    }
  | {
      type: "mutation_started";
      conversationId: string;
      mutationId: string;
      action: ConversationActivityPatch["action"];
      revision: number;
      activeView: boolean;
    }
  | {
      type: "mutation_succeeded";
      conversationId: string;
      mutationId: string;
      activity: ConversationActivity;
    }
  | {
      type: "mutation_failed";
      conversationId: string;
      mutationId: string;
    }
  | {
      type: "view_epoch_reset";
      conversationId: string;
    }
  | {
      type: "announcement_acknowledged";
      conversationId: string;
      key: string;
    }
  | { type: "account_reset" };

const EMPTY_RECORD: ConversationActivityRecord = {
  canonical: null,
  serverRevision: 0,
  request: null,
  mutation: null,
  manualUnreadGuardSource: null,
  manualUnreadGuardGeneration: 0,
  announcement: null,
  announcementFingerprint: "none",
  announcementGeneration: 0,
  acknowledgedAnnouncements: {},
};

const PRESENTATION_RANK: Record<ConversationActivityPresentation, number> = {
  none: 0,
  manual_unread: 1,
  new_activity: 2,
  needs_input: 3,
  needs_attention: 4,
  working: 5,
};

const isKnownActiveStatus = (value: unknown): value is ActiveOperationStatus =>
  value === "queued" || value === "running" || value === "checking";

const isKnownIdleStatus = (value: unknown): value is "idle" => value === "idle";

const canonicalOperationIsWorking = (
  activity: ConversationActivity | null,
): boolean => {
  const status: unknown = activity?.operation.status;
  if (status == null || isKnownIdleStatus(status)) {
    return false;
  }
  return isKnownActiveStatus(status) || typeof status === "string";
};

const canonicalAttentionPresentation = (
  activity: ConversationActivity | null,
): Exclude<ConversationActivityPresentation, "working"> => {
  const status: unknown = activity?.attention.status;
  switch (status) {
    case undefined:
    case null:
    case "none":
      return "none";
    case "needs_attention":
      return "needs_attention";
    case "needs_input":
      return "needs_input";
    case "new_activity":
      return "new_activity";
    case "manual_unread":
      return "manual_unread";
    default:
      return "needs_attention";
  }
};

const currentMutationForRecord = (
  record: ConversationActivityRecord,
): ConversationActivityMutationRecord | null =>
  record.mutation && record.serverRevision <= record.mutation.issuedRevision
    ? record.mutation
    : null;

const canonicalAttentionIsUnread = (
  activity: ConversationActivity | null,
): boolean => {
  const status: unknown = activity?.attention.status;
  return status !== undefined && status !== null && status !== "none";
};

const presentationForRecord = (
  record: ConversationActivityRecord | undefined,
): ConversationActivityPresentation => {
  if (!record) {
    return "none";
  }
  if (record.request || canonicalOperationIsWorking(record.canonical)) {
    return "working";
  }

  const canonical = canonicalAttentionPresentation(record.canonical);
  const currentMutation = currentMutationForRecord(record);
  if (currentMutation?.action === "mark_read") {
    return "none";
  }
  if (currentMutation?.action === "mark_unread") {
    return PRESENTATION_RANK[canonical] > PRESENTATION_RANK.manual_unread
      ? canonical
      : "manual_unread";
  }
  return canonical;
};

const announcementFingerprintForRecord = (
  record: ConversationActivityRecord,
): string => {
  const presentation = presentationForRecord(record);
  if (presentation === "none") {
    return "none";
  }

  if (presentation === "working") {
    const identity = record.request
      ? `${record.request.requestId}:${record.request.status}`
      : [
          record.canonical?.operation.kind ?? "unknown",
          record.canonical?.operation.status ?? "checking",
          record.canonical?.operation.updated_at ?? "unknown",
        ].join(":");
    return `working:${identity}`;
  }

  return `${presentation}:${record.canonical?.attention.cursor ?? "no-cursor"}`;
};

const withAnnouncement = (
  conversationId: string,
  previous: ConversationActivityRecord,
  record: ConversationActivityRecord,
  preserveIfPresentationUnchanged = false,
): ConversationActivityRecord => {
  const presentation = presentationForRecord(record);
  const previousPresentation = presentationForRecord(previous);
  const computedFingerprint = announcementFingerprintForRecord(record);
  const preserve =
    preserveIfPresentationUnchanged && presentation === previousPresentation;
  const fingerprint = computedFingerprint;
  const generation =
    preserve || fingerprint === previous.announcementFingerprint
      ? previous.announcementGeneration
      : previous.announcementGeneration + 1;
  const existingTransitionContinues =
    presentation !== "none" &&
    (preserve || fingerprint === previous.announcementFingerprint) &&
    previous.announcement !== null;
  return {
    ...record,
    announcementFingerprint: fingerprint,
    announcementGeneration: generation,
    announcement:
      presentation === "none"
        ? null
        : existingTransitionContinues
          ? previous.announcement
        : {
            key: `${conversationId}:${generation}:${fingerprint}`,
            presentation,
          },
  };
};

const recordFor = (
  state: ConversationActivityState,
  conversationId: string,
): ConversationActivityRecord => state.byConversationId[conversationId] ?? EMPTY_RECORD;

const replaceRecord = (
  state: ConversationActivityState,
  conversationId: string,
  record: ConversationActivityRecord,
  preserveAnnouncementIfPresentationUnchanged = false,
): ConversationActivityState => ({
  byConversationId: {
    ...state.byConversationId,
    [conversationId]: withAnnouncement(
      conversationId,
      recordFor(state, conversationId),
      record,
      preserveAnnouncementIfPresentationUnchanged,
    ),
  },
});

export const createConversationActivityState = (): ConversationActivityState => ({
  byConversationId: {},
});

export function conversationActivityReducer(
  state: ConversationActivityState,
  action: ConversationActivityAction,
): ConversationActivityState {
  if (action.type === "account_reset") {
    return createConversationActivityState();
  }

  const current = recordFor(state, action.conversationId);

  switch (action.type) {
    case "server_projection_merged": {
      if (action.revision <= current.serverRevision) {
        return state;
      }
      const previousAttention = canonicalAttentionPresentation(current.canonical);
      const nextAttention = canonicalAttentionPresentation(action.activity);
      let guardSource = current.manualUnreadGuardSource;
      let guardGeneration = current.manualUnreadGuardGeneration;
      if (
        action.activeView === true &&
        previousAttention !== "manual_unread" &&
        nextAttention === "manual_unread"
      ) {
        guardSource = "server";
        guardGeneration += 1;
      }
      return replaceRecord(state, action.conversationId, {
        ...current,
        canonical: action.activity,
        serverRevision: action.revision,
        request:
          current.request &&
          current.request.transportFinishedRevision !== null &&
          action.revision > current.request.transportFinishedRevision &&
          isKnownIdleStatus(action.activity.operation.status)
            ? null
            : current.request,
        manualUnreadGuardSource: guardSource,
        manualUnreadGuardGeneration: guardGeneration,
      });
    }
    case "request_started":
      return replaceRecord(state, action.conversationId, {
        ...current,
        request: {
          requestId: action.requestId,
          status: action.status,
          kind: action.kind,
          issuedRevision: action.revision,
          transportFinishedRevision: null,
        },
      });
    case "request_progressed":
      if (current.request?.requestId !== action.requestId) {
        return state;
      }
      return replaceRecord(state, action.conversationId, {
        ...current,
        request: { ...current.request, status: action.status },
      });
    case "request_transport_finished":
      if (current.request?.requestId !== action.requestId) {
        return state;
      }
      return replaceRecord(state, action.conversationId, {
        ...current,
        request: {
          ...current.request,
          status: "checking",
          transportFinishedRevision: action.revision,
        },
      });
    case "request_retired":
      if (current.request?.requestId !== action.requestId) {
        return state;
      }
      return replaceRecord(state, action.conversationId, {
        ...current,
        request: null,
      });
    case "mutation_started":
      return replaceRecord(state, action.conversationId, {
        ...current,
        mutation: {
          mutationId: action.mutationId,
          action: action.action,
          issuedRevision: action.revision,
          guardGenerationAtStart: current.manualUnreadGuardGeneration,
        },
        manualUnreadGuardSource:
          action.action === "mark_unread" && action.activeView
            ? action.mutationId
            : current.manualUnreadGuardSource,
        manualUnreadGuardGeneration:
          action.action === "mark_unread" && action.activeView
            ? current.manualUnreadGuardGeneration + 1
            : current.manualUnreadGuardGeneration,
      });
    case "mutation_succeeded": {
      if (current.mutation?.mutationId !== action.mutationId) {
        return state;
      }
      const responseIsCurrent =
        current.serverRevision <= current.mutation.issuedRevision;
      const canonical = responseIsCurrent ? action.activity : current.canonical;
      const serverRevision = responseIsCurrent
        ? Math.max(current.serverRevision, current.mutation.issuedRevision) + 1
        : current.serverRevision;
      const responseAttention = canonicalAttentionPresentation(canonical);
      let guardSource = current.manualUnreadGuardSource;
      if (
        current.mutation.action === "mark_read" &&
        current.manualUnreadGuardGeneration ===
          current.mutation.guardGenerationAtStart
      ) {
        guardSource = null;
      }
      return replaceRecord(
        state,
        action.conversationId,
        {
          ...current,
          canonical,
          serverRevision,
          mutation: null,
          manualUnreadGuardSource: guardSource,
        },
        responseAttention === presentationForRecord(current),
      );
    }
    case "mutation_failed":
      if (current.mutation?.mutationId !== action.mutationId) {
        return state;
      }
      return replaceRecord(state, action.conversationId, {
        ...current,
        mutation: null,
        manualUnreadGuardSource:
          current.manualUnreadGuardSource === action.mutationId
            ? null
            : current.manualUnreadGuardSource,
      });
    case "view_epoch_reset":
      if (current.manualUnreadGuardSource == null) {
        return state;
      }
      return replaceRecord(state, action.conversationId, {
        ...current,
        manualUnreadGuardSource: null,
      });
    case "announcement_acknowledged":
      if (
        !state.byConversationId[action.conversationId] ||
        !action.key ||
        current.acknowledgedAnnouncements[action.key]
      ) {
        return state;
      }
      return replaceRecord(state, action.conversationId, {
        ...current,
        acknowledgedAnnouncements: {
          ...current.acknowledgedAnnouncements,
          [action.key]: true,
        },
      });
  }
}

export const selectConversationActivityPresentation = (
  state: ConversationActivityState,
  conversationId: string | null | undefined,
): ConversationActivityPresentation =>
  conversationId
    ? presentationForRecord(state.byConversationId[conversationId])
    : "none";

export const selectConversationHasEffectiveUnread = (
  state: ConversationActivityState,
  conversationId: string | null | undefined,
): boolean => {
  if (!conversationId) return false;
  const record = state.byConversationId[conversationId];
  if (!record) return false;
  const currentMutation = currentMutationForRecord(record);
  if (currentMutation?.action === "mark_read") return false;
  if (currentMutation?.action === "mark_unread") return true;
  return canonicalAttentionIsUnread(record.canonical);
};

export const selectConversationAttentionCursor = (
  state: ConversationActivityState,
  conversationId: string | null | undefined,
): string | null =>
  conversationId
    ? state.byConversationId[conversationId]?.canonical?.attention.cursor ?? null
    : null;

export const selectAggregateConversationActivityPresentation = (
  state: ConversationActivityState,
  conversationIds: readonly string[] = Object.keys(state.byConversationId),
): ConversationActivityPresentation => {
  let selected: ConversationActivityPresentation = "none";
  for (const conversationId of conversationIds) {
    const presentation = selectConversationActivityPresentation(state, conversationId);
    if (PRESENTATION_RANK[presentation] > PRESENTATION_RANK[selected]) {
      selected = presentation;
    }
  }
  return selected;
};

export const selectConversationIsLocked = (
  state: ConversationActivityState,
  conversationId: string | null | undefined,
): boolean => {
  if (!conversationId) {
    return false;
  }
  const record = state.byConversationId[conversationId];
  return Boolean(record?.request || canonicalOperationIsWorking(record?.canonical ?? null));
};

export const selectConversationRequestIsCurrent = (
  state: ConversationActivityState,
  conversationId: string,
  requestId: string,
): boolean => state.byConversationId[conversationId]?.request?.requestId === requestId;

export const selectManualUnreadGuard = (
  state: ConversationActivityState,
  conversationId: string | null | undefined,
): boolean =>
  Boolean(
    conversationId &&
      state.byConversationId[conversationId]?.manualUnreadGuardSource,
  );

export const selectConversationAnnouncement = (
  state: ConversationActivityState,
  conversationId: string | null | undefined,
): ConversationActivityAnnouncement | null => {
  if (!conversationId) {
    return null;
  }
  const record = state.byConversationId[conversationId];
  const announcement = record?.announcement;
  if (!record || !announcement || record.acknowledgedAnnouncements[announcement.key]) {
    return null;
  }
  return announcement;
};
