import { createClient } from "@/lib/supabase-server";
import {
  handleRecoveryRequest,
  RecoveryAttemptLimiter,
} from "@/lib/recovery-request";

const RECOVERY_ATTEMPT_LIMIT = 5;
const RECOVERY_GLOBAL_ATTEMPT_LIMIT = 100;
const RECOVERY_ATTEMPT_WINDOW_MS = 10 * 60 * 1_000;
const limiter = new RecoveryAttemptLimiter({
  limit: RECOVERY_ATTEMPT_LIMIT,
  windowMs: RECOVERY_ATTEMPT_WINDOW_MS,
});
const globalLimiter = new RecoveryAttemptLimiter({
  limit: RECOVERY_GLOBAL_ATTEMPT_LIMIT,
  windowMs: RECOVERY_ATTEMPT_WINDOW_MS,
  maxTrackedKeys: 1,
});

export async function POST(request: Request) {
  return handleRecoveryRequest(request, {
    configuredAppOrigin: process.env.ARGUS_APP_ORIGIN,
    environment: process.env.NODE_ENV,
    limiter,
    globalLimiter,
    async sendRecovery(email, redirectTo) {
      const supabase = await createClient();
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo,
      });
      if (error) throw error;
    },
  });
}
