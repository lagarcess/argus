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
  }
}

const TELEMETRY_INGEST_ENABLED =
  process.env.NEXT_PUBLIC_TELEMETRY_INGEST_ENABLED !== "false";

function enqueueTelemetryEvent(payload: FunnelEventPayload): void {
  if (typeof window === "undefined") {
    return;
  }

  window.__argusTelemetryQueue = window.__argusTelemetryQueue ?? [];
  window.__argusTelemetryQueue.push(payload);
}

function sendTelemetryEvent(payload: FunnelEventPayload): void {
  if (!TELEMETRY_INGEST_ENABLED) {
    enqueueTelemetryEvent(payload);
    return;
  }

  void postTelemetryEvents({
    body: payload,
    throwOnError: true,
  }).catch(() => {
    // Keep local queue as fallback when network/backend is unavailable.
    enqueueTelemetryEvent(payload);
  });
}

export function trackFunnelEvent(
  event: FunnelEventName,
  properties?: FunnelEventPayload["properties"],
): FunnelEventPayload {
  const payload: FunnelEventPayload = {
    event,
    timestamp: new Date().toISOString(),
    properties,
  };

  sendTelemetryEvent(payload);

  return payload;
}
