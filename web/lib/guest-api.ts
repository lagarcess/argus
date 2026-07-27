import {
  apiFetch,
  persistBrowserSession,
  type AuthResponsePayload,
  type Conversation,
} from "@/lib/argus-api";
import { getSupabaseClient } from "@/lib/supabase-client";
import type { GuestPendingActionSummary } from "@/lib/guest-conversion";

export async function createGuestHandoff(payload: {
  destination_email: string;
  source_conversation_id: string;
  pending_action?: GuestPendingActionSummary | null;
}) {
  return apiFetch<{ handoff_id: string; expires_at: string }>(
    "/auth/guest/handoffs",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function linkGuestIdentity(payload: {
  email: string;
  password: string;
}) {
  const supabase = getSupabaseClient();
  if (!supabase) {
    throw new Error("Supabase auth client is unavailable for account creation.");
  }
  const { data, error } = await supabase.auth.getSession();
  const session = data.session;
  if (error || !session?.access_token || !session.refresh_token) {
    throw new Error("The current guest session is unavailable.");
  }
  const response = await apiFetch<
    AuthResponsePayload & { account_kind: "registered" }
  >("/auth/guest/link", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${session.access_token}`,
    },
    body: JSON.stringify({
      ...payload,
      refresh_token: session.refresh_token,
    }),
  });
  await persistBrowserSession(response);
  return response;
}

export async function replaceGuestConversation() {
  return apiFetch<{ conversation: Conversation }>(
    "/conversations/guest/replace",
    { method: "POST" },
  );
}
