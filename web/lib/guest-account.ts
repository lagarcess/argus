import type { OnboardingStage, PrimaryGoal } from "./argus-api";

export type ApiUser = {
  id: string;
  email: string | null;
  username: string | null;
  display_name: string | null;
  language: "en" | "es-419";
  locale: "en-US" | "es-419";
  onboarding: {
    completed: boolean;
    stage: OnboardingStage;
    language_confirmed: boolean;
    primary_goal: PrimaryGoal | null;
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
