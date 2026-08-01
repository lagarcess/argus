import { describe, expect, test } from "bun:test";
import { renderToStaticMarkup } from "react-dom/server";

import {
  ConversationActivityIndicator,
  conversationActivityLabelDescriptor,
} from "../components/chat/ConversationActivityIndicator";
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

const relativeLuminance = (hex: string): number => {
  const [red, green, blue] = hex
    .match(/.{2}/g)!
    .map((channel) => Number.parseInt(channel, 16) / 255)
    .map((channel) =>
      channel <= 0.04045
        ? channel / 12.92
        : ((channel + 0.055) / 1.055) ** 2.4,
    );
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
};

const contrastRatio = (foreground: string, background: string): number => {
  const foregroundLuminance = relativeLuminance(foreground);
  const backgroundLuminance = relativeLuminance(background);
  return (
    (Math.max(foregroundLuminance, backgroundLuminance) + 0.05) /
    (Math.min(foregroundLuminance, backgroundLuminance) + 0.05)
  );
};

describe("ConversationActivityIndicator", () => {
  test("uses typed queued and checking labels while running stays working", () => {
    expect(conversationActivityLabelDescriptor("working", "queued")).toEqual({
      key: "chat.activity.queued",
      defaultValue: "Queued",
    });
    expect(conversationActivityLabelDescriptor("working", "checking")).toEqual({
      key: "chat.activity.checking",
      defaultValue: "Checking status",
    });
    expect(conversationActivityLabelDescriptor("working", "working")).toEqual({
      key: "chat.activity.working",
      defaultValue: "Working",
    });
  });

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
    const lightToken = html.match(/text-\[#([\da-f]{6})\]/i)?.[1];

    expect(html).toContain("lucide-circle-help");
    expect(lightToken).toBeDefined();
    expect(contrastRatio(lightToken!, "ffffff")).toBeGreaterThanOrEqual(3);
    expect(contrastRatio(lightToken!, "f2f2f2")).toBeGreaterThanOrEqual(3);
    expect(html).toContain("dark:text-[#9ab9dc]");
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
