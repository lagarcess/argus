import {
  apiFetch,
  persistBrowserSession,
  type AuthResponsePayload,
  type Conversation,
} from "@/lib/argus-api";
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
  const response = await apiFetch<
    AuthResponsePayload & { account_kind: "registered" }
  >("/auth/guest/link", {
    method: "POST",
    body: JSON.stringify(payload),
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
