import { describe, expect, test } from "bun:test";

import type { ConversationActivity } from "../lib/argus-api";
import {
  conversationActivityReducer,
  createConversationActivityState,
  selectAggregateConversationActivityPresentation,
  selectConversationActivityPresentation,
  selectConversationAttentionCursor,
  selectConversationAnnouncement,
  selectConversationHasEffectiveUnread,
  selectConversationIsLocked,
  selectConversationOperationLabel,
  selectConversationRequestIsCurrent,
  selectManualUnreadGuard,
} from "../lib/conversation-activity-state";

const activity = (
  operation: ConversationActivity["operation"]["status"] = "idle",
  attention: ConversationActivity["attention"]["status"] = "none",
  cursor: string | null = null,
): ConversationActivity => ({
  operation: {
    status: operation,
    kind: operation === "idle" ? null : "chat_turn",
    updated_at: operation === "idle" ? null : `2026-08-01T12:00:0${operation.length}Z`,
  },
  attention: { status: attention, cursor },
});

describe("conversation activity presentation", () => {
  test("selects the local operation label before canonical queued running or checking truth", () => {
    let state = createConversationActivityState();
    for (const [status, expected] of [
      ["queued", "queued"],
      ["running", "working"],
      ["checking", "checking"],
    ] as const) {
      state = conversationActivityReducer(state, {
        type: "server_projection_merged",
        conversationId: status,
        activity: activity(status),
        revision: 1,
      });
      expect(selectConversationOperationLabel(state, status)).toBe(expected);
    }

    state = conversationActivityReducer(state, {
      type: "request_started",
      conversationId: "running",
      requestId: "local-queued",
      status: "queued",
      kind: "chat_turn",
      revision: 2,
    });
    expect(selectConversationOperationLabel(state, "running")).toBe("queued");
    expect(selectConversationOperationLabel(state, "missing")).toBeNull();
  });

  test("selects effective unread independently from working presentation", () => {
    let state = createConversationActivityState();
    const unreadStatuses = [
      "new_activity",
      "manual_unread",
      "needs_input",
      "needs_attention",
    ] as const;

    for (const attention of unreadStatuses) {
      state = conversationActivityReducer(state, {
        type: "server_projection_merged",
        conversationId: attention,
        activity: activity("running", attention, `cursor-${attention}`),
        revision: 1,
      });
      expect(selectConversationActivityPresentation(state, attention)).toBe(
        "working",
      );
      expect(selectConversationHasEffectiveUnread(state, attention)).toBe(true);
      expect(selectConversationAttentionCursor(state, attention)).toBe(
        `cursor-${attention}`,
      );
    }

    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "read",
      activity: activity("running", "none"),
      revision: 1,
    });
    expect(selectConversationHasEffectiveUnread(state, "read")).toBe(false);
    expect(selectConversationAttentionCursor(state, "read")).toBeNull();
  });

  test("applies only the current optimistic read intent to effective unread", () => {
    let state = createConversationActivityState();
    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity("running", "new_activity", "cursor-current"),
      revision: 1,
    });
    state = conversationActivityReducer(state, {
      type: "mutation_started",
      conversationId: "conversation-a",
      mutationId: "read-1",
      action: "mark_read",
      revision: 2,
      activeView: true,
    });
    expect(selectConversationHasEffectiveUnread(state, "conversation-a")).toBe(
      false,
    );
    expect(selectConversationAttentionCursor(state, "conversation-a")).toBe(
      "cursor-current",
    );

    state = conversationActivityReducer(state, {
      type: "mutation_started",
      conversationId: "conversation-a",
      mutationId: "unread-2",
      action: "mark_unread",
      revision: 3,
      activeView: true,
    });
    expect(selectConversationHasEffectiveUnread(state, "conversation-a")).toBe(
      true,
    );
  });

  test("uses the locked precedence for canonical and optimistic conflicts", () => {
    const attentionCases = [
      ["needs_attention", "needs_attention"],
      ["needs_input", "needs_input"],
      ["new_activity", "new_activity"],
      ["manual_unread", "manual_unread"],
      ["none", "none"],
    ] as const;

    for (const [attention, expected] of attentionCases) {
      let state = createConversationActivityState();
      state = conversationActivityReducer(state, {
        type: "server_projection_merged",
        conversationId: attention,
        activity: activity("idle", attention, `cursor-${attention}`),
        revision: 1,
      });
      expect(selectConversationActivityPresentation(state, attention)).toBe(expected);

      state = conversationActivityReducer(state, {
        type: "request_started",
        conversationId: attention,
        requestId: "request-1",
        status: "queued",
        kind: "chat_turn",
        revision: 2,
      });
      expect(selectConversationActivityPresentation(state, attention)).toBe("working");
    }

    let state = createConversationActivityState();
    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "attention-wins",
      activity: activity("idle", "needs_attention", "cursor-attention"),
      revision: 1,
    });
    state = conversationActivityReducer(state, {
      type: "mutation_started",
      conversationId: "attention-wins",
      mutationId: "mutation-1",
      action: "mark_unread",
      revision: 2,
      activeView: false,
    });
    expect(selectConversationActivityPresentation(state, "attention-wins")).toBe(
      "needs_attention",
    );
  });

  test("keeps selected-row presentation independent and aggregates without counts", () => {
    let state = createConversationActivityState();
    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "selected",
      activity: activity("idle", "manual_unread", "cursor-selected"),
      revision: 1,
    });
    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "question",
      activity: activity("idle", "needs_input", "cursor-question"),
      revision: 1,
    });

    expect(selectConversationActivityPresentation(state, "selected")).toBe(
      "manual_unread",
    );
    expect(
      selectAggregateConversationActivityPresentation(state, ["selected", "question"]),
    ).toBe("needs_input");

    state = conversationActivityReducer(state, {
      type: "request_started",
      conversationId: "working",
      requestId: "request-working",
      status: "running",
      kind: "chat_turn",
      revision: 2,
    });
    expect(
      selectAggregateConversationActivityPresentation(state, [
        "selected",
        "question",
        "working",
      ]),
    ).toBe("working");
    expect(selectConversationActivityPresentation(state, "selected")).toBe(
      "manual_unread",
    );
  });

  test("uses the same precedence for every pair in the aggregate", () => {
    const presentations = [
      "none",
      "manual_unread",
      "new_activity",
      "needs_input",
      "needs_attention",
      "working",
    ] as const;
    const rank = new Map(presentations.map((presentation, index) => [presentation, index]));
    let state = createConversationActivityState();

    for (const presentation of presentations) {
      const conversationId = `pair-${presentation}`;
      if (presentation === "working") {
        state = conversationActivityReducer(state, {
          type: "request_started",
          conversationId,
          requestId: "request-working",
          status: "running",
          kind: "chat_turn",
          revision: 1,
        });
      } else {
        state = conversationActivityReducer(state, {
          type: "server_projection_merged",
          conversationId,
          activity: activity("idle", presentation, `cursor-${presentation}`),
          revision: 1,
        });
      }
    }

    for (const left of presentations) {
      for (const right of presentations) {
        const expected = (rank.get(left) ?? 0) >= (rank.get(right) ?? 0) ? left : right;
        expect(
          selectAggregateConversationActivityPresentation(state, [
            `pair-${left}`,
            `pair-${right}`,
          ]),
        ).toBe(expected);
      }
    }
  });

  test("fails unknown runtime values safe instead of treating them as complete", () => {
    let state = createConversationActivityState();
    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "unknown-operation",
      activity: activity("future_status" as ConversationActivity["operation"]["status"]),
      revision: 1,
    });
    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "unknown-attention",
      activity: activity(
        "idle",
        "future_attention" as ConversationActivity["attention"]["status"],
      ),
      revision: 1,
    });

    expect(selectConversationActivityPresentation(state, "unknown-operation")).toBe(
      "working",
    );
    expect(selectConversationActivityPresentation(state, "unknown-attention")).toBe(
      "needs_attention",
    );
  });
});

describe("conversation-scoped request ownership", () => {
  test("locks only the requested conversations and rejects late callbacks", () => {
    let state = createConversationActivityState();
    state = conversationActivityReducer(state, {
      type: "request_started",
      conversationId: "conversation-a",
      requestId: "request-a1",
      status: "queued",
      kind: "chat_turn",
      revision: 1,
    });
    state = conversationActivityReducer(state, {
      type: "request_started",
      conversationId: "conversation-b",
      requestId: "request-b1",
      status: "running",
      kind: "backtest_job",
      revision: 2,
    });
    state = conversationActivityReducer(state, {
      type: "request_started",
      conversationId: "conversation-a",
      requestId: "request-a2",
      status: "running",
      kind: "chat_turn",
      revision: 3,
    });

    expect(selectConversationIsLocked(state, "conversation-a")).toBe(true);
    expect(selectConversationIsLocked(state, "conversation-b")).toBe(true);
    expect(selectConversationIsLocked(state, "conversation-c")).toBe(false);
    expect(
      selectConversationRequestIsCurrent(state, "conversation-a", "request-a1"),
    ).toBe(false);
    expect(
      selectConversationRequestIsCurrent(state, "conversation-a", "request-a2"),
    ).toBe(true);

    const afterLateProgress = conversationActivityReducer(state, {
      type: "request_progressed",
      conversationId: "conversation-a",
      requestId: "request-a1",
      status: "checking",
    });
    const afterLateRetirement = conversationActivityReducer(afterLateProgress, {
      type: "request_retired",
      conversationId: "conversation-a",
      requestId: "request-a1",
    });
    expect(afterLateRetirement).toBe(state);
    expect(selectConversationIsLocked(afterLateRetirement, "conversation-a")).toBe(true);
    expect(selectConversationIsLocked(afterLateRetirement, "conversation-b")).toBe(true);

    const afterCurrentRetirement = conversationActivityReducer(afterLateRetirement, {
      type: "request_retired",
      conversationId: "conversation-a",
      requestId: "request-a2",
    });
    expect(selectConversationIsLocked(afterCurrentRetirement, "conversation-a")).toBe(false);
    expect(selectConversationIsLocked(afterCurrentRetirement, "conversation-b")).toBe(true);
  });

  test("settles only from canonical idle strictly newer than transport completion", () => {
    let state = createConversationActivityState();
    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity(),
      revision: 2,
    });
    state = conversationActivityReducer(state, {
      type: "request_started",
      conversationId: "conversation-a",
      requestId: "request-a",
      status: "queued",
      kind: "chat_turn",
      revision: 5,
    });

    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity(),
      revision: 6,
    });
    expect(selectConversationIsLocked(state, "conversation-a")).toBe(true);

    state = conversationActivityReducer(state, {
      type: "request_transport_finished",
      conversationId: "conversation-a",
      requestId: "request-a",
      revision: 7,
    });
    expect(state.byConversationId["conversation-a"]?.request).toMatchObject({
      status: "checking",
      transportFinishedRevision: 7,
    });

    const afterTransportFinished = state;
    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity(),
      revision: 6,
    });
    expect(state).toBe(afterTransportFinished);
    expect(selectConversationIsLocked(state, "conversation-a")).toBe(true);

    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity(),
      revision: 7,
    });
    expect(selectConversationIsLocked(state, "conversation-a")).toBe(true);

    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity("queued"),
      revision: 8,
    });
    expect(selectConversationIsLocked(state, "conversation-a")).toBe(true);

    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity("running"),
      revision: 9,
    });
    expect(selectConversationIsLocked(state, "conversation-a")).toBe(true);

    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity(),
      revision: 10,
    });
    expect(selectConversationIsLocked(state, "conversation-a")).toBe(false);
  });
});

describe("optimistic activity mutations", () => {
  test("protects newer canonical projections from stale mutation success", () => {
    let state = createConversationActivityState();
    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity("idle", "new_activity", "cursor-1"),
      revision: 1,
    });
    state = conversationActivityReducer(state, {
      type: "mutation_started",
      conversationId: "conversation-a",
      mutationId: "read-1",
      action: "mark_read",
      revision: 2,
      activeView: true,
    });
    expect(selectConversationActivityPresentation(state, "conversation-a")).toBe("none");

    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity("idle", "needs_attention", "cursor-2"),
      revision: 3,
      activeView: true,
    });
    expect(selectConversationActivityPresentation(state, "conversation-a")).toBe(
      "needs_attention",
    );
    state = conversationActivityReducer(state, {
      type: "mutation_succeeded",
      conversationId: "conversation-a",
      mutationId: "read-1",
      activity: activity("idle", "none"),
    });

    expect(selectConversationActivityPresentation(state, "conversation-a")).toBe(
      "needs_attention",
    );
  });

  test("ignores equal and older server revisions without changing state", () => {
    let state = createConversationActivityState();
    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity("idle", "new_activity", "cursor-new"),
      revision: 4,
    });

    const equal = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity("idle", "none"),
      revision: 4,
    });
    const older = conversationActivityReducer(equal, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity("idle", "needs_input", "cursor-old"),
      revision: 3,
    });

    expect(equal).toBe(state);
    expect(older).toBe(state);
    expect(selectConversationActivityPresentation(older, "conversation-a")).toBe(
      "new_activity",
    );
  });

  test("ignores stale responses and rolls back only the current failed mutation", () => {
    let state = createConversationActivityState();
    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity("idle", "new_activity", "cursor-1"),
      revision: 1,
    });
    state = conversationActivityReducer(state, {
      type: "mutation_started",
      conversationId: "conversation-a",
      mutationId: "unread-old",
      action: "mark_unread",
      revision: 2,
      activeView: true,
    });
    state = conversationActivityReducer(state, {
      type: "mutation_started",
      conversationId: "conversation-a",
      mutationId: "read-new",
      action: "mark_read",
      revision: 3,
      activeView: true,
    });

    const afterStaleFailure = conversationActivityReducer(state, {
      type: "mutation_failed",
      conversationId: "conversation-a",
      mutationId: "unread-old",
    });
    expect(afterStaleFailure).toBe(state);
    expect(selectConversationActivityPresentation(afterStaleFailure, "conversation-a")).toBe(
      "none",
    );

    const afterRollback = conversationActivityReducer(afterStaleFailure, {
      type: "mutation_failed",
      conversationId: "conversation-a",
      mutationId: "read-new",
    });
    expect(selectConversationActivityPresentation(afterRollback, "conversation-a")).toBe(
      "new_activity",
    );
  });
});

describe("same-view guard and announcements", () => {
  test("arms on manual unread in the active view and clears only on a view epoch reset", () => {
    let state = createConversationActivityState();
    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity("idle", "none"),
      revision: 1,
      activeView: true,
    });
    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity("idle", "manual_unread", "cursor-1"),
      revision: 2,
      activeView: true,
    });
    expect(selectManualUnreadGuard(state, "conversation-a")).toBe(true);

    state = conversationActivityReducer(state, {
      type: "view_epoch_reset",
      conversationId: "conversation-a",
    });
    expect(selectManualUnreadGuard(state, "conversation-a")).toBe(false);

    state = conversationActivityReducer(state, {
      type: "mutation_started",
      conversationId: "conversation-a",
      mutationId: "unread-1",
      action: "mark_unread",
      revision: 3,
      activeView: true,
    });
    expect(selectManualUnreadGuard(state, "conversation-a")).toBe(true);

    state = conversationActivityReducer(state, { type: "account_reset" });
    expect(selectManualUnreadGuard(state, "conversation-a")).toBe(false);
  });

  test("keeps a server-armed guard through every newer terminal projection", () => {
    for (const attention of [
      "new_activity",
      "needs_input",
      "needs_attention",
    ] as const) {
      let state = createConversationActivityState();
      state = conversationActivityReducer(state, {
        type: "server_projection_merged",
        conversationId: attention,
        activity: activity("idle", "none"),
        revision: 1,
        activeView: true,
      });
      state = conversationActivityReducer(state, {
        type: "server_projection_merged",
        conversationId: attention,
        activity: activity("idle", "manual_unread", "cursor-manual"),
        revision: 2,
        activeView: true,
      });
      state = conversationActivityReducer(state, {
        type: "server_projection_merged",
        conversationId: attention,
        activity: activity("idle", attention, `cursor-${attention}`),
        revision: 3,
        activeView: true,
      });

      expect(selectManualUnreadGuard(state, attention)).toBe(true);
      expect(selectConversationActivityPresentation(state, attention)).toBe(attention);
    }
  });

  test("does not let an older successful read clear a newer server guard", () => {
    let state = createConversationActivityState();
    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity("idle", "new_activity", "cursor-1"),
      revision: 1,
      activeView: true,
    });
    state = conversationActivityReducer(state, {
      type: "mutation_started",
      conversationId: "conversation-a",
      mutationId: "stale-read",
      action: "mark_read",
      revision: 2,
      activeView: true,
    });
    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity("idle", "manual_unread", "cursor-2"),
      revision: 3,
      activeView: true,
    });
    expect(selectManualUnreadGuard(state, "conversation-a")).toBe(true);
    expect(selectConversationActivityPresentation(state, "conversation-a")).toBe(
      "manual_unread",
    );

    state = conversationActivityReducer(state, {
      type: "mutation_succeeded",
      conversationId: "conversation-a",
      mutationId: "stale-read",
      activity: activity("idle", "none"),
    });

    expect(selectManualUnreadGuard(state, "conversation-a")).toBe(true);
    expect(selectConversationActivityPresentation(state, "conversation-a")).toBe(
      "manual_unread",
    );
  });

  test("offers each meaningful transition announcement once", () => {
    let state = createConversationActivityState();
    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity("idle", "new_activity", "cursor-1"),
      revision: 1,
    });

    const first = selectConversationAnnouncement(state, "conversation-a");
    expect(first).toMatchObject({ presentation: "new_activity" });
    expect(first?.key).toContain("cursor-1");

    state = conversationActivityReducer(state, {
      type: "announcement_acknowledged",
      conversationId: "conversation-a",
      key: first?.key ?? "",
    });
    expect(selectConversationAnnouncement(state, "conversation-a")).toBeNull();

    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity("idle", "new_activity", "cursor-1"),
      revision: 2,
    });
    expect(selectConversationAnnouncement(state, "conversation-a")).toBeNull();

    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity("idle", "needs_input", "cursor-2"),
      revision: 3,
    });
    expect(selectConversationAnnouncement(state, "conversation-a")).toMatchObject({
      presentation: "needs_input",
    });
  });

  test("announces a repeated manual-unread transition after an intervening read", () => {
    let state = createConversationActivityState();
    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity("idle", "none"),
      revision: 1,
      activeView: true,
    });
    state = conversationActivityReducer(state, {
      type: "mutation_started",
      conversationId: "conversation-a",
      mutationId: "unread-1",
      action: "mark_unread",
      revision: 2,
      activeView: true,
    });
    const first = selectConversationAnnouncement(state, "conversation-a");
    expect(first).toMatchObject({ presentation: "manual_unread" });
    state = conversationActivityReducer(state, {
      type: "announcement_acknowledged",
      conversationId: "conversation-a",
      key: first?.key ?? "",
    });
    state = conversationActivityReducer(state, {
      type: "mutation_succeeded",
      conversationId: "conversation-a",
      mutationId: "unread-1",
      activity: activity("idle", "manual_unread", "cursor-confirmed"),
    });
    expect(selectConversationAnnouncement(state, "conversation-a")).toBeNull();
    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity("idle", "manual_unread", "cursor-confirmed"),
      revision: 4,
      activeView: true,
    });
    expect(selectConversationAnnouncement(state, "conversation-a")).toBeNull();

    state = conversationActivityReducer(state, {
      type: "mutation_started",
      conversationId: "conversation-a",
      mutationId: "read-1",
      action: "mark_read",
      revision: 5,
      activeView: true,
    });
    state = conversationActivityReducer(state, {
      type: "mutation_succeeded",
      conversationId: "conversation-a",
      mutationId: "read-1",
      activity: activity("idle", "none"),
    });
    state = conversationActivityReducer(state, {
      type: "mutation_started",
      conversationId: "conversation-a",
      mutationId: "unread-2",
      action: "mark_unread",
      revision: 6,
      activeView: true,
    });

    const second = selectConversationAnnouncement(state, "conversation-a");
    expect(second).toMatchObject({ presentation: "manual_unread" });
    expect(second?.key).not.toBe(first?.key);
  });

  test("ignores a late announcement acknowledgment after account reset", () => {
    let state = createConversationActivityState();
    state = conversationActivityReducer(state, {
      type: "server_projection_merged",
      conversationId: "conversation-a",
      activity: activity("idle", "new_activity", "cursor-1"),
      revision: 1,
    });
    const key = selectConversationAnnouncement(state, "conversation-a")?.key ?? "";
    state = conversationActivityReducer(state, { type: "account_reset" });

    const afterLateAck = conversationActivityReducer(state, {
      type: "announcement_acknowledged",
      conversationId: "conversation-a",
      key,
    });
    expect(afterLateAck).toBe(state);
    expect(afterLateAck.byConversationId).toEqual({});
  });
});
