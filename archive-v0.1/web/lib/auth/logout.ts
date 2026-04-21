import { postAuthLogout } from "@/lib/api/sdk.gen";
import { supabase } from "@/lib/supabase";
import { trackFunnelEvent, FUNNEL_EVENTS } from "@/lib/telemetry";

export async function performLogout(): Promise<void> {
  trackFunnelEvent(FUNNEL_EVENTS.LOGOUT);

  try {
    await postAuthLogout();
  } catch {
    // noop: local fallback must still execute
  }

  await supabase.auth.signOut();
}
