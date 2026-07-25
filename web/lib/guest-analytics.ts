import { apiFetch } from "@/lib/argus-api";
import type { GuestConversionReason } from "@/lib/guest-conversion";
import type { ArgusLanguage } from "@/lib/language-features";

export type GuestFunnelClientEventInput =
  | {
      event: "starter_action_selected";
      language: ArgusLanguage;
      surface: "starter_actions";
      strategy_category: "buy_and_hold" | "dca_accumulation";
      terminal_outcome: "selected";
    }
  | {
      event: "conversion_prompt_shown";
      language: ArgusLanguage;
      surface: "conversion_modal";
      conversion_reason: GuestConversionReason;
      terminal_outcome: "shown";
    };

export function buildGuestFunnelClientEvent(
  input: GuestFunnelClientEventInput,
) {
  return {
    event: input.event,
    language: input.language,
    surface: input.surface,
    ...("strategy_category" in input
      ? { strategy_category: input.strategy_category }
      : {}),
    ...("conversion_reason" in input
      ? { conversion_reason: input.conversion_reason }
      : {}),
    terminal_outcome: input.terminal_outcome,
  };
}

export function captureGuestFunnelEvent(
  input: GuestFunnelClientEventInput,
): void {
  void apiFetch<{ success: boolean }>("/analytics/guest-events", {
    method: "POST",
    body: JSON.stringify(buildGuestFunnelClientEvent(input)),
  }).catch(() => undefined);
}
