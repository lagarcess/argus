import { describe, expect, test } from "bun:test";

import type { ConversationActivity } from "../lib/argus-api";
import {
  conversationActivityReducer,
  createConversationActivityState,
  selectAggregateConversationActivityPresentation,
  selectConversationActivityPresentation,
  selectConversationAnnouncement,
  selectConversationIsLocked,
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
    });
    state = conversationActivityReducer(state, {
      type: "request_started",
      conversationId: "conversation-b",
      requestId: "request-b1",
      status: "running",
      kind: "backtest_job",
    });
    state = conversationActivityReducer(state, {
      type: "request_started",
      conversationId: "conversation-a",
      requestId: "request-a2",
      status: "running",
      kind: "chat_turn",
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
    const afterLateSettle = conversationActivityReducer(afterLateProgress, {
      type: "request_settled",
      conversationId: "conversation-a",
      requestId: "request-a1",
    });
    expect(afterLateSettle).toBe(state);
    expect(selectConversationIsLocked(afterLateSettle, "conversation-a")).toBe(true);
    expect(selectConversationIsLocked(afterLateSettle, "conversation-b")).toBe(true);

    const afterCurrentSettle = conversationActivityReducer(afterLateSettle, {
      type: "request_settled",
      conversationId: "conversation-a",
      requestId: "request-a2",
    });
    expect(selectConversationIsLocked(afterCurrentSettle, "conversation-a")).toBe(false);
    expect(selectConversationIsLocked(afterCurrentSettle, "conversation-b")).toBe(true);
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
});
