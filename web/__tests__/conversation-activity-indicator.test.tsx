import { describe, expect, test } from "bun:test";
import { renderToStaticMarkup } from "react-dom/server";

import { ConversationActivityIndicator } from "../components/chat/ConversationActivityIndicator";
import type { ConversationActivity } from "../lib/argus-api";
import {
  conversationActivityReducer,
  createConversationActivityState,
  selectConversationActivityPresentation,
  type ConversationActivityPresentation,
} from "../lib/conversation-activity-state";
import { inlineFailureTextClass } from "../lib/failure-treatment";

const renderIndicator = (
  presentation: ConversationActivityPresentation,
): string =>
  renderToStaticMarkup(
    <ConversationActivityIndicator presentation={presentation} />,
  );

describe("ConversationActivityIndicator", () => {
  test("renders the existing selector's winning state when work covers unread attention", () => {
    const canonical: ConversationActivity = {
      operation: { status: "idle", kind: null, updated_at: null },
      attention: { status: "needs_attention", cursor: "attention-1" },
    };
    let state = conversationActivityReducer(createConversationActivityState(), {
      type: "server_projection_merged",
      conversationId: "conversation-1",
      activity: canonical,
      revision: 1,
    });
    state = conversationActivityReducer(state, {
      type: "request_started",
      conversationId: "conversation-1",
      requestId: "request-1",
      status: "running",
      kind: "chat_turn",
      revision: 2,
    });

    const html = renderIndicator(
      selectConversationActivityPresentation(state, "conversation-1"),
    );

    expect(html).toContain('data-conversation-activity="working"');
    expect(html).toContain("lucide-loader-circle");
    expect(html).not.toContain("lucide-circle-alert");
  });

  test("uses a calm open ring and disables its motion for reduced-motion users", () => {
    const html = renderIndicator("working");

    expect(html).toContain("lucide-loader-circle");
    expect(html).toContain("animate-spin");
    expect(html).toContain("motion-reduce:animate-none");
    expect(html).toContain('aria-hidden="true"');
  });

  test("reuses the shared PR 320 failure token for needs attention", () => {
    const html = renderIndicator("needs_attention");

    expect(html).toContain("lucide-circle-alert");
    for (const token of inlineFailureTextClass.split(" ")) {
      expect(html).toContain(token);
    }
  });

  test("keeps needs input static and visually distinct from failure", () => {
    const html = renderIndicator("needs_input");

    expect(html).toContain("lucide-circle-help");
    expect(html).toContain("text-[#7da0ca]");
    expect(html).not.toContain("lucide-circle-alert");
    expect(html).not.toContain("animate-");
  });

  test("uses the established teal dot for automatic and manual unread", () => {
    for (const presentation of ["new_activity", "manual_unread"] as const) {
      const html = renderIndicator(presentation);
      expect(html).toContain('data-activity-dot="true"');
      expect(html).toContain("bg-[#70a38d]");
      expect(html).toContain("dark:bg-[#9bc6b4]");
    }
  });

  test("renders no decorative marker for idle read conversations", () => {
    expect(renderIndicator("none")).toBe("");
  });
});
