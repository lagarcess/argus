import { API_URL } from "@/lib/api";
import { postTelemetryEvents } from "@/lib/api/sdk.gen";

export const FUNNEL_EVENTS = {
  ONBOARDING_COMPLETE: "onboarding_complete",
  DRAFT_SUCCESS: "draft_success",
  DRAFT_FAIL: "draft_fail",
  DRAFT_SAVED: "draft_saved",
  BACKTEST_SUCCESS: "backtest_success",
  BACKTEST_FAIL: "backtest_fail",
  LOGOUT: "logout",
} as const;

export type FunnelEventName = (typeof FUNNEL_EVENTS)[keyof typeof FUNNEL_EVENTS];

export type FunnelEventPayload = {
  event: FunnelEventName;
  timestamp: string;
  properties?: Record<string, string | number | boolean | null | undefined>;
};

declare global {
  interface Window {
    __argusTelemetryQueue?: FunnelEventPayload[];
    __argusTelemetryFlushing?: boolean;
  }
}

async function sendTelemetryEvent(payload: FunnelEventPayload): Promise<boolean> {
  const result = await postTelemetryEvents({
    baseUrl: API_URL,
    credentials: "include",
    body: payload,
  });

  return Boolean(result.response?.ok);
}

async function flushTelemetryQueue(): Promise<void> {
  if (typeof window === "undefined") {
    return;
  }
  window.__argusTelemetryQueue = window.__argusTelemetryQueue ?? [];

  if (window.__argusTelemetryFlushing) {
    return;
  }
  window.__argusTelemetryFlushing = true;

  try {
    while (window.__argusTelemetryQueue.length > 0) {
      const next = window.__argusTelemetryQueue[0];
      if (!next) {
        break;
      }
      try {
        const sent = await sendTelemetryEvent(next);
        if (!sent) {
          break;
        }
        window.__argusTelemetryQueue.shift();
      } catch {
        // Keep queue in memory as fallback when network/backend are unavailable.
        break;
      }
    }
  } finally {
    window.__argusTelemetryFlushing = false;
  }
}

export function trackFunnelEvent(
  event: FunnelEventName,
  properties?: FunnelEventPayload["properties"]
): FunnelEventPayload {
  const payload: FunnelEventPayload = {
    event,
    timestamp: new Date().toISOString(),
    properties,
  };

  if (typeof window !== "undefined") {
    window.__argusTelemetryQueue = window.__argusTelemetryQueue ?? [];
    window.__argusTelemetryQueue.push(payload);
    void flushTelemetryQueue();
  }

  return payload;
}
