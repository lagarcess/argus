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
  }

  return payload;
}
