import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  buildGuestFunnelClientEvent,
  type GuestFunnelClientEventInput,
} from "../lib/guest-analytics";

const root = join(import.meta.dir, "..");

describe("guest funnel analytics", () => {
  test("builds only the approved browser-owned properties", () => {
    const unsafe = {
      event: "starter_action_selected",
      language: "es-419",
      surface: "starter_actions",
      strategy_category: "buy_and_hold",
      terminal_outcome: "selected",
      prompt: "Buy $100,000 of AAPL",
      assistant_prose: "Private response",
      email: "person@example.com",
      conversation_title: "Private title",
      cookie: "secret",
      ip_address: "203.0.113.8",
      url: "https://argus.test/chat?token=secret",
      model: "internal-model",
      provider: "internal-provider",
    } as unknown as GuestFunnelClientEventInput;

    expect(buildGuestFunnelClientEvent(unsafe)).toEqual({
      event: "starter_action_selected",
      language: "es-419",
      surface: "starter_actions",
      strategy_category: "buy_and_hold",
      terminal_outcome: "selected",
    });
  });

  test("routes starter identity to the authenticated send owner without prompt analytics", () => {
    const starter = readFileSync(
      join(root, "components/chat/StarterActions.tsx"),
      "utf-8",
    );
    const guestExperience = readFileSync(
      join(root, "components/guest/useGuestExperience.ts"),
      "utf-8",
    );

    expect(starter).toContain("strategy_category");
    expect(starter).toMatch(/onSelect\(value,\s*metadata\)/);
    expect(starter).toContain("metadata: { strategy_category:");
    expect(starter).not.toContain("captureGuestFunnelEvent");
    expect(guestExperience).toContain('event: "starter_action_selected"');
    expect(guestExperience).toContain("strategy_category");
  });

  test("records each conversion exposure with its typed reason", () => {
    const conversion = readFileSync(
      join(root, "components/guest/useGuestConversion.ts"),
      "utf-8",
    );

    expect(conversion).toContain('"conversion_prompt_shown"');
    expect(conversion).toContain("conversion_reason: nextReason");
    expect(conversion).toContain('surface: "conversion_modal"');
  });

  test("sends browser events only through the authenticated API envelope", () => {
    const analytics = readFileSync(
      join(root, "lib/guest-analytics.ts"),
      "utf-8",
    );

    expect(analytics).toContain('"/analytics/guest-events"');
    expect(analytics).toContain("apiFetch");
    for (const forbidden of [
      "localStorage",
      "document.cookie",
      "posthog.capture",
      "authorization",
      "access_token",
      "refresh_token",
    ]) {
      expect(analytics.toLowerCase()).not.toContain(forbidden.toLowerCase());
    }
  });
});
