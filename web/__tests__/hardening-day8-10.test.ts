import { afterEach, beforeEach, describe, expect, it, mock } from "bun:test";
import {
  builderToStrategyCreatePayload,
  strategyToBuilderForm,
} from "../lib/strategy-mapper";
import { resolveOnboardingRedirect } from "../lib/onboarding-guard";
import { FUNNEL_EVENTS, trackFunnelEvent } from "../lib/telemetry";

describe("onboarding gate + redirect", () => {
  it("redirects incomplete onboarding users to onboarding", () => {
    expect(
      resolveOnboardingRedirect({
        onboardingCompleted: false,
        pathname: "/builder",
      }),
    ).toBe("/onboarding");
  });

  it("redirects completed onboarding users away from onboarding", () => {
    expect(
      resolveOnboardingRedirect({
        onboardingCompleted: true,
        pathname: "/onboarding",
      }),
    ).toBe("/builder");
  });
});

describe("save draft persistence + edit hydration", () => {
  it("maps builder draft to strategy payload for persistence", () => {
    const payload = builderToStrategyCreatePayload({
      name: "Mean Reversion",
      asset_symbol: "AAPL",
      timeframe: "1H",
      period_start: "2026-03-01",
      period_end: "2026-03-15",
      parameters: { rsi_period: 14 },
      entry_criteria: [{ indicator_a: "RSI_14", operator: "lt", value: 30 }],
      exit_criteria: [{ indicator_a: "RSI_14", operator: "gt", value: 60 }],
      slippage_bps: 10,
      fees_per_trade_bps: 5,
      capital: 100000,
      trade_direction: "LONG",
      participation_rate: 0.1,
      execution_priority: 1,
      va_sensitivity: 1,
      slippage_model: "vol_adjusted",
    });

    expect(payload.symbols).toEqual(["AAPL"]);
    expect(payload.timeframe).toBe("1Hour");
    expect(payload.slippage).toBe(0.001);
    expect(payload.fees).toBe(0.0005);
  });

  it("hydrates builder edit form from persisted strategy", () => {
    const hydrated = strategyToBuilderForm({
      name: "Draft from DB",
      symbols: ["BTC/USD"],
      timeframe: "4Hour",
      start_date: "2026-01-01T00:00:00.000Z",
      end_date: "2026-01-31T00:00:00.000Z",
      entry_criteria: [
        {
          indicator_a: "EMA_20",
          operator: "cross_above",
          indicator_b: "EMA_50",
        },
      ],
      exit_criteria: [
        {
          indicator_a: "EMA_20",
          operator: "cross_below",
          indicator_b: "EMA_50",
        },
      ],
      slippage: 0.001,
      fees: 0.0005,
      indicators_config: { ema_fast: 20 },
    });

    expect(hydrated.asset_symbol).toBe("BTC/USD");
    expect(hydrated.timeframe).toBe("4H");
    expect(hydrated.period_start).toBe("2026-01-01");
    expect(hydrated.period_end).toBe("2026-01-31");
  });
});

describe("logout backend-first with local fallback", () => {
  beforeEach(() => {
    mock.restore();
  });

  afterEach(() => {
    mock.restore();
  });

  it("always clears local session even when backend logout fails", async () => {
    const signOut = mock(async () => ({}));

    mock.module("../lib/api/sdk.gen", () => ({
      postAuthLogout: mock(async () => {
        throw new Error("network down");
      }),
    }));

    mock.module("../lib/supabase", () => ({
      supabase: {
        auth: {
          signOut,
        },
      },
    }));

    const { performLogout } = await import("../lib/auth/logout");
    await performLogout();

    expect(signOut).toHaveBeenCalledTimes(1);
  });
});

describe("minimal funnel telemetry checkpoints", () => {
  beforeEach(() => {
    (globalThis as unknown as { window?: Window }).window = globalThis as unknown as Window;
    (globalThis as unknown as { __argusTelemetryQueue?: unknown[] }).__argusTelemetryQueue = [];
    (globalThis as unknown as { __argusTelemetryFlushing?: boolean }).__argusTelemetryFlushing = false;
  });

  it("defines all release-critical events", () => {
    expect(Object.values(FUNNEL_EVENTS)).toEqual(
      expect.arrayContaining([
        "onboarding_complete",
        "draft_success",
        "draft_fail",
        "draft_saved",
        "backtest_success",
        "backtest_fail",
        "logout",
      ]),
    );
  });

  it("records checkpoint payloads", () => {
    const payload = trackFunnelEvent(FUNNEL_EVENTS.DRAFT_SUCCESS, {
      source: "test",
    });
    expect(payload.event).toBe("draft_success");
    expect(payload.properties?.source).toBe("test");
  });

  it("sends telemetry events to backend sink", async () => {
    const fetchMock = mock(() =>
      Promise.resolve(new Response(null, { status: 202 })),
    );
    (globalThis as unknown as { fetch: typeof fetch }).fetch = fetchMock;

    trackFunnelEvent(FUNNEL_EVENTS.DRAFT_SUCCESS, { source: "unit-test" });
    for (let i = 0; i < 20 && fetchMock.mock.calls.length === 0; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 10));
    }

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [request] = fetchMock.mock.calls[0] as [Request];
    expect(request.url).toContain("/telemetry/events");
    expect(request.method).toBe("POST");
  });

  it("keeps event queued when telemetry sink is unavailable", async () => {
    const fetchMock = mock(() => Promise.reject(new Error("network down")));
    (globalThis as unknown as { fetch: typeof fetch }).fetch = fetchMock;

    trackFunnelEvent(FUNNEL_EVENTS.DRAFT_FAIL, { reason: "network_error" });
    await Promise.resolve();
    await Promise.resolve();

    const queue = (globalThis as unknown as { __argusTelemetryQueue?: unknown[] })
      .__argusTelemetryQueue;
    expect(Array.isArray(queue)).toBe(true);
    expect(queue?.length).toBe(1);
  });
});
