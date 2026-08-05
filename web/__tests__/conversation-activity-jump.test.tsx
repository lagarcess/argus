import { describe, expect, test } from "bun:test";
import { renderToStaticMarkup } from "react-dom/server";

import { ConversationActivityJumpButton } from "../components/chat/ConversationActivityJumpButton";
import type { ConversationActivityPresentation } from "../lib/conversation-activity-state";
import { inlineFailureTextClass } from "../lib/failure-treatment";

const labels = {
  latest: "Jump to latest",
  working: "Jump to latest; Argus is working below",
  unread: "Jump to new activity",
  needsInput: "Jump to the latest question",
  needsAttention: "Jump to the latest recovery",
} as const;

const renderJump = (presentation: ConversationActivityPresentation): string =>
  renderToStaticMarkup(
    <ConversationActivityJumpButton
      presentation={presentation}
      labels={labels}
      onJump={() => undefined}
    />,
  );

describe("ConversationActivityJumpButton", () => {
  test("keeps ordinary history as one 44px down-arrow control", () => {
    const html = renderJump("none");

    expect(html.match(/<button/g)).toHaveLength(1);
    expect(html).toContain('aria-label="Jump to latest"');
    expect(html).toContain("h-11 w-11");
    expect(html).toContain("lucide-arrow-down");
    expect(html).not.toContain("data-activity-dot");
  });

  test("replaces the arrow with a restrained three-dot wave while work is below", () => {
    const html = renderJump("working");

    expect(html).toContain(
      'aria-label="Jump to latest; Argus is working below"',
    );
    expect(html.match(/data-working-dot=/g)).toHaveLength(3);
    expect(html).toContain("animate-bounce");
    expect(html).toContain("motion-reduce:animate-none");
    expect(html).not.toContain("lucide-arrow-down");
  });

  test("uses the arrow plus the established teal marker for both unread states", () => {
    for (const presentation of ["new_activity", "manual_unread"] as const) {
      const html = renderJump(presentation);
      expect(html).toContain('aria-label="Jump to new activity"');
      expect(html).toContain("lucide-arrow-down");
      expect(html).toContain('data-activity-dot="true"');
      expect(html).toContain("bg-[#70a38d]");
    }
  });

  test("uses a distinct question marker and localized label for needs input", () => {
    const html = renderJump("needs_input");

    expect(html).toContain('aria-label="Jump to the latest question"');
    expect(html).toContain("lucide-arrow-down");
    expect(html).toContain("lucide-circle-help");
    expect(html).not.toContain("lucide-circle-alert");
  });

  test("uses the shared failure treatment and localized label for recovery", () => {
    const html = renderJump("needs_attention");

    expect(html).toContain('aria-label="Jump to the latest recovery"');
    expect(html).toContain("lucide-arrow-down");
    expect(html).toContain("lucide-circle-alert");
    for (const token of inlineFailureTextClass.split(" ")) {
      expect(html).toContain(token);
    }
  });
});
