import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { chatHttpErrorDisplay } from "../components/chat/chat-message-projection";
import {
  GUEST_COMPUTE_CLAIM_MESSAGE_KEY,
  GUEST_COMPUTE_CLAIM_RETRY_IN_KEY,
  GUEST_COMPUTE_CLAIM_UNAVAILABLE_CODE,
  guestComputeClaimTransportPatch,
  localizedGuestComputeClaimMessage,
} from "../lib/guest-compute-claim-error";
import { recoveryDisplayText } from "../lib/chat-recovery-display";
import {
  parseRetryAfterSeconds,
  remainingRetryAfterSeconds,
  RETRY_AFTER_FALLBACK_SECONDS,
  RETRY_AFTER_MAX_SECONDS,
  RETRY_AFTER_MIN_SECONDS,
} from "../lib/retry-after";

const root = join(import.meta.dir, "..");
const enCatalog = JSON.parse(
  readFileSync(join(root, "public/locales/en/common.json"), "utf8"),
) as Record<string, unknown>;
const esCatalog = JSON.parse(
  readFileSync(join(root, "public/locales/es-419/common.json"), "utf8"),
) as Record<string, unknown>;

const RAW_SERVER_DETAIL = "Argus could not start this turn. Please try again.";
const EN_COPY = "Argus could not start this turn. Try again in a moment.";
const ES_COPY = "Argus no pudo iniciar este turno. Inténtalo de nuevo en un momento.";
const EM_DASH = "\u2014";

function tFromCatalog(catalog: Record<string, unknown>) {
  return (key: string, options?: Record<string, unknown> | string) => {
    const values =
      typeof options === "object" && options !== null
        ? options
        : ({} as Record<string, unknown>);
    const count = values.count;
    const pluralKey =
      typeof count === "number"
        ? count === 1
          ? `${key}_one`
          : `${key}_other`
        : key;
    const template = pluralKey
      .split(".")
      .reduce<unknown>(
        (value, segment) =>
          typeof value === "object" && value !== null && !Array.isArray(value)
            ? (value as Record<string, unknown>)[segment]
            : undefined,
        catalog,
      );
    if (typeof template !== "string") {
      return key;
    }
    return template.replace(/\{\{(\w+)\}\}/g, (_, name: string) =>
      String(values[name] ?? ""),
    );
  };
}

function catalogString(
  catalog: Record<string, unknown>,
  key: string,
): string {
  const value = key.split(".").reduce<unknown>((current, segment) => {
    if (typeof current !== "object" || current === null) return undefined;
    return (current as Record<string, unknown>)[segment];
  }, catalog);
  if (typeof value !== "string") {
    throw new Error(`missing locale string ${key}`);
  }
  return value;
}

describe("Retry-After parsing", () => {
  test("reads delta-seconds", () => {
    expect(parseRetryAfterSeconds("15")).toBe(15);
    expect(parseRetryAfterSeconds("1")).toBe(1);
    expect(parseRetryAfterSeconds("120")).toBe(120);
  });

  test("reads an HTTP-date relative to now", () => {
    const nowMs = Date.parse("Fri, 25 Sep 2026 12:00:00 GMT");
    expect(
      parseRetryAfterSeconds("Fri, 25 Sep 2026 12:00:08 GMT", nowMs),
    ).toBe(8);
  });

  test("falls back when the header is missing or garbage", () => {
    expect(parseRetryAfterSeconds(null)).toBe(RETRY_AFTER_FALLBACK_SECONDS);
    expect(parseRetryAfterSeconds(undefined)).toBe(RETRY_AFTER_FALLBACK_SECONDS);
    expect(parseRetryAfterSeconds("")).toBe(RETRY_AFTER_FALLBACK_SECONDS);
    expect(parseRetryAfterSeconds("   ")).toBe(RETRY_AFTER_FALLBACK_SECONDS);
    expect(parseRetryAfterSeconds("soon")).toBe(RETRY_AFTER_FALLBACK_SECONDS);
    expect(parseRetryAfterSeconds("15s")).toBe(RETRY_AFTER_FALLBACK_SECONDS);
    expect(parseRetryAfterSeconds("not-a-http-date")).toBe(
      RETRY_AFTER_FALLBACK_SECONDS,
    );
  });

  test("clamps huge, zero, and past values into 1..120", () => {
    expect(parseRetryAfterSeconds("0")).toBe(RETRY_AFTER_MIN_SECONDS);
    expect(parseRetryAfterSeconds("999999")).toBe(RETRY_AFTER_MAX_SECONDS);
    const nowMs = Date.parse("Fri, 25 Sep 2026 12:00:00 GMT");
    expect(
      parseRetryAfterSeconds("Wed, 21 Oct 2015 07:28:00 GMT", nowMs),
    ).toBe(RETRY_AFTER_MIN_SECONDS);
    expect(
      parseRetryAfterSeconds("Fri, 25 Sep 2026 16:00:00 GMT", nowMs),
    ).toBe(RETRY_AFTER_MAX_SECONDS);
  });

  test("remaining seconds never go negative", () => {
    expect(remainingRetryAfterSeconds(undefined, 1_000)).toBe(0);
    expect(remainingRetryAfterSeconds(1_500, 1_000)).toBe(1);
    expect(remainingRetryAfterSeconds(500, 1_000)).toBe(0);
  });
});

describe("guest compute claim error copy", () => {
  test("maps the 503 claim code to English and es-419 catalogs", () => {
    const projected = chatHttpErrorDisplay(
      GUEST_COMPUTE_CLAIM_UNAVAILABLE_CODE,
      RAW_SERVER_DETAIL,
    );

    expect(projected.content).toBe("");
    expect(projected.recoveryDisplay).toEqual({
      kind: "recovery_code",
      code: GUEST_COMPUTE_CLAIM_UNAVAILABLE_CODE,
    });
    expect(
      recoveryDisplayText(projected.recoveryDisplay, tFromCatalog(enCatalog)),
    ).toBe(EN_COPY);
    expect(
      recoveryDisplayText(projected.recoveryDisplay, tFromCatalog(esCatalog)),
    ).toBe(ES_COPY);
    expect(
      recoveryDisplayText(projected.recoveryDisplay, tFromCatalog(enCatalog)),
    ).not.toBe(RAW_SERVER_DETAIL);
    expect(
      recoveryDisplayText(projected.recoveryDisplay, tFromCatalog(esCatalog)),
    ).not.toContain(RAW_SERVER_DETAIL);
  });

  test("never renders raw server text for the claim code", () => {
    expect(
      localizedGuestComputeClaimMessage(
        GUEST_COMPUTE_CLAIM_UNAVAILABLE_CODE,
        tFromCatalog(enCatalog),
        RAW_SERVER_DETAIL,
      ),
    ).toBe(EN_COPY);
    expect(
      localizedGuestComputeClaimMessage(
        GUEST_COMPUTE_CLAIM_UNAVAILABLE_CODE,
        tFromCatalog(esCatalog),
        RAW_SERVER_DETAIL,
      ),
    ).toBe(ES_COPY);
    expect(
      localizedGuestComputeClaimMessage(
        "stream_interrupted",
        tFromCatalog(enCatalog),
        RAW_SERVER_DETAIL,
      ),
    ).toBe(RAW_SERVER_DETAIL);
  });

  test("keeps unrelated HTTP errors on the backend message", () => {
    expect(
      chatHttpErrorDisplay("artifact_action_invalid_state", RAW_SERVER_DETAIL),
    ).toEqual({
      content: RAW_SERVER_DETAIL,
      recoveryDisplay: null,
    });
  });

  test("new claim strings contain no em dash", () => {
    const keys = [
      GUEST_COMPUTE_CLAIM_MESSAGE_KEY,
      `${GUEST_COMPUTE_CLAIM_RETRY_IN_KEY}_one`,
      `${GUEST_COMPUTE_CLAIM_RETRY_IN_KEY}_other`,
    ];
    for (const catalog of [enCatalog, esCatalog]) {
      for (const key of keys) {
        const value = catalogString(catalog, key);
        expect(value, key).not.toContain(EM_DASH);
        expect(value.includes("—"), key).toBe(false);
      }
    }
  });

  test("attaches one retry control that waits for Retry-After", () => {
    const nowMs = Date.parse("Fri, 25 Sep 2026 12:00:00 GMT");
    const patch = guestComputeClaimTransportPatch({
      code: GUEST_COMPUTE_CLAIM_UNAVAILABLE_CODE,
      retryAfterHeader: "8",
      retryAction: {
        id: "retry-last-turn",
        label: "Retry",
        labelKey: "common.retry",
        type: "retry_last_turn",
        payload: { message: "Compare Apple with SPY" },
      },
      nowMs,
    });

    expect(patch?.assistantRecoveryCode).toBe(
      GUEST_COMPUTE_CLAIM_UNAVAILABLE_CODE,
    );
    expect(patch?.actions?.[0]?.availableAtMs).toBe(nowMs + 8_000);
    expect(patch?.actions?.[0]?.payload).toEqual({
      message: "Compare Apple with SPY",
    });
    expect(
      guestComputeClaimTransportPatch({
        code: "too_many_requests",
        retryAfterHeader: "8",
        retryAction: {
          id: "retry-last-turn",
          label: "Retry",
          type: "retry_last_turn",
        },
      }),
    ).toEqual({});
  });

  test("countdown labels localize without raw server text", () => {
    expect(
      tFromCatalog(enCatalog)(GUEST_COMPUTE_CLAIM_RETRY_IN_KEY, { count: 1 }),
    ).toBe("Retry in 1 second");
    expect(
      tFromCatalog(enCatalog)(GUEST_COMPUTE_CLAIM_RETRY_IN_KEY, { count: 15 }),
    ).toBe("Retry in 15 seconds");
    expect(
      tFromCatalog(esCatalog)(GUEST_COMPUTE_CLAIM_RETRY_IN_KEY, { count: 1 }),
    ).toBe("Reintentar en 1 segundo");
    expect(
      tFromCatalog(esCatalog)(GUEST_COMPUTE_CLAIM_RETRY_IN_KEY, { count: 15 }),
    ).toBe("Reintentar en 15 segundos");
  });
});
