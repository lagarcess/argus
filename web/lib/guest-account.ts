import type { AvatarTheme } from "./avatar-theme";

type LegacyOnboardingStage =
  | "language_selection"
  | "primary_goal_selection"
  | "ready"
  | "completed";

type LegacyPrimaryGoal =
  | "learn_basics"
  | "build_passive_strategy"
  | "test_stock_idea"
  | "explore_crypto"
  | "surprise_me";

export type ApiUser = {
  id: string;
  email: string | null;
  username: string | null;
  display_name: string | null;
  language: "en" | "es-419";
  locale: "en-US" | "es-419";
  avatar_theme?: AvatarTheme;
  onboarding: {
    completed: boolean;
    stage: LegacyOnboardingStage;
    language_confirmed: boolean;
    primary_goal: LegacyPrimaryGoal | null;
  };
};

export type GuestAccountSummary = {
  expires_at: string;
  conversation_limit: number;
  message_limit: number;
  simulation_limit: number;
  feedback_limit: number;
};

export type AccountCapabilities = {
  can_create_additional_conversation: boolean;
  can_manage_conversation: boolean;
  can_save_decision: boolean;
  can_manage_account: boolean;
  can_use_omnisearch: boolean;
  can_search_current_workspace: boolean;
  can_use_grounded_discovery: boolean;
  can_submit_feedback: boolean;
};

export type UserResponse = {
  user: ApiUser;
  account_kind: "guest" | "registered";
  guest: GuestAccountSummary | null;
  capabilities: AccountCapabilities;
  public_account_access_enabled: boolean;
};

export type GuestProfileProbeOutcome = "bootstrap_required" | "fail_closed";

export function guestProfileProbeOutcome(
  error: unknown,
): GuestProfileProbeOutcome {
  if (typeof error !== "object" || error === null) return "fail_closed";
  const status = "status" in error ? error.status : undefined;
  const code = "code" in error ? error.code : undefined;
  if (status === 401) return "bootstrap_required";
  if (status === 403 && code === "guest_session_expired") {
    return "bootstrap_required";
  }
  return "fail_closed";
}
