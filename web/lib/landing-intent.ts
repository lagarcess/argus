import {
  readSessionStored,
  readStored,
  removeSessionStored,
  writeSessionStored,
  writeStored,
} from "./browser-storage";

/**
 * First-touch campaign capture for ad landings.
 *
 * Semantics:
 * - Persist the first non-empty value for each field. A later visit cannot
 *   overwrite a stored field, and an empty visit cannot clear one. That keeps
 *   "which ad brought this person in" stable through return trips and signup.
 * - `starter` on the stored attribution object follows the same first-touch
 *   rule. Composer prefill is a separate consume-once session intent written
 *   from this visit's URL, so a later `starter=` can still prefill without
 *   rewriting first-touch attribution.
 * - Values are trimmed, stripped of control characters, and length-capped.
 *   `starter` is a whitelist (`backtest` | `savings`); anything else is dropped
 *   so a link can never inject free text into the composer or a model request.
 */

export const LANDING_INTENT_STORAGE_KEY = "argus:landing-intent:v1";
export const LANDING_STARTER_STORAGE_KEY = "argus:landing-starter:v1";

export const LANDING_STARTERS = ["backtest", "savings"] as const;
export type LandingStarter = (typeof LANDING_STARTERS)[number];

export const ATTRIBUTION_FIELDS = [
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_content",
  "fbclid",
  "ref",
  "starter",
  "landing_path",
] as const;

export type AttributionField = (typeof ATTRIBUTION_FIELDS)[number];

export type LandingIntent = {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  fbclid?: string;
  ref?: string;
  starter?: LandingStarter;
  landing_path?: string;
};

export type AttributionPayload = {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  fbclid?: string;
  ref?: string;
  starter?: string;
  landing_path?: string;
};

const VALUE_MAX_LENGTH = 256;
const PATH_MAX_LENGTH = 200;
const TOKEN_PATTERN = /^[\w.%+\-]+$/;

const LANDING_STARTER_COPY_KEYS = {
  backtest: "chat.landing_starters.backtest",
  savings: "chat.landing_starters.savings",
} as const;

export const LANDING_STARTER_COPY_FALLBACKS = {
  backtest: "What if I had bought an S&P 500 fund over the last 12 months?",
  savings: "If I set aside $200 every month, what would that add up to in a year?",
} as const;

function sanitizeToken(
  value: string | null | undefined,
  maxLength = VALUE_MAX_LENGTH,
): string | undefined {
  if (typeof value !== "string") return undefined;
  const cleaned = value.replace(/[\u0000-\u001F\u007F]/g, "").trim();
  if (!cleaned || !TOKEN_PATTERN.test(cleaned)) return undefined;
  return cleaned.slice(0, maxLength);
}

export function sanitizeLandingStarter(
  value: string | null | undefined,
): LandingStarter | undefined {
  const cleaned = sanitizeToken(value, 32)?.toLowerCase();
  return cleaned === "backtest" || cleaned === "savings" ? cleaned : undefined;
}

export function sanitizeLandingPath(
  value: string | null | undefined,
): string | undefined {
  if (typeof value !== "string") return undefined;
  const cleaned = value.replace(/[\u0000-\u001F\u007F]/g, "").trim();
  if (!cleaned.startsWith("/") || cleaned.startsWith("//") || cleaned.includes("://")) {
    return undefined;
  }
  const path = cleaned.split("?")[0]?.split("#")[0] ?? "";
  if (!path.startsWith("/") || path.startsWith("//") || path.length > PATH_MAX_LENGTH) {
    return undefined;
  }
  return path;
}

function withDefinedFields(intent: LandingIntent): LandingIntent {
  const next: LandingIntent = {};
  if (intent.utm_source) next.utm_source = intent.utm_source;
  if (intent.utm_medium) next.utm_medium = intent.utm_medium;
  if (intent.utm_campaign) next.utm_campaign = intent.utm_campaign;
  if (intent.utm_content) next.utm_content = intent.utm_content;
  if (intent.fbclid) next.fbclid = intent.fbclid;
  if (intent.ref) next.ref = intent.ref;
  if (intent.starter) next.starter = intent.starter;
  if (intent.landing_path) next.landing_path = intent.landing_path;
  return next;
}

export function parseLandingIntent(
  search: string | URLSearchParams,
  landingPath?: string,
): LandingIntent {
  const params =
    typeof search === "string"
      ? new URLSearchParams(search.startsWith("?") ? search.slice(1) : search)
      : search;
  return withDefinedFields({
    utm_source: sanitizeToken(params.get("utm_source")),
    utm_medium: sanitizeToken(params.get("utm_medium")),
    utm_campaign: sanitizeToken(params.get("utm_campaign")),
    utm_content: sanitizeToken(params.get("utm_content")),
    fbclid: sanitizeToken(params.get("fbclid")),
    ref: sanitizeToken(params.get("ref")),
    starter: sanitizeLandingStarter(params.get("starter")),
    landing_path: sanitizeLandingPath(landingPath),
  });
}

export function isEmptyLandingIntent(
  intent: LandingIntent | AttributionPayload | null | undefined,
): boolean {
  if (!intent) return true;
  return ATTRIBUTION_FIELDS.every((field) => !intent[field]);
}

export function mergeFirstTouchLandingIntent(
  existing: LandingIntent | null,
  incoming: LandingIntent,
): LandingIntent {
  const current = existing ?? {};
  return withDefinedFields({
    utm_source: current.utm_source ?? incoming.utm_source,
    utm_medium: current.utm_medium ?? incoming.utm_medium,
    utm_campaign: current.utm_campaign ?? incoming.utm_campaign,
    utm_content: current.utm_content ?? incoming.utm_content,
    fbclid: current.fbclid ?? incoming.fbclid,
    ref: current.ref ?? incoming.ref,
    starter: current.starter ?? incoming.starter,
    landing_path: current.landing_path ?? incoming.landing_path,
  });
}

function sanitizeStoredIntent(raw: Record<string, unknown>): LandingIntent | null {
  const intent = withDefinedFields({
    utm_source: sanitizeToken(typeof raw.utm_source === "string" ? raw.utm_source : undefined),
    utm_medium: sanitizeToken(typeof raw.utm_medium === "string" ? raw.utm_medium : undefined),
    utm_campaign: sanitizeToken(typeof raw.utm_campaign === "string" ? raw.utm_campaign : undefined),
    utm_content: sanitizeToken(typeof raw.utm_content === "string" ? raw.utm_content : undefined),
    fbclid: sanitizeToken(typeof raw.fbclid === "string" ? raw.fbclid : undefined),
    ref: sanitizeToken(typeof raw.ref === "string" ? raw.ref : undefined),
    starter: sanitizeLandingStarter(typeof raw.starter === "string" ? raw.starter : undefined),
    landing_path: sanitizeLandingPath(typeof raw.landing_path === "string" ? raw.landing_path : undefined),
  });
  return isEmptyLandingIntent(intent) ? null : intent;
}

export function readLandingIntent(): LandingIntent | null {
  try {
    const raw = readStored(LANDING_INTENT_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return null;
    return sanitizeStoredIntent(parsed as Record<string, unknown>);
  } catch {
    return null;
  }
}

const STARTER_CONSUMED_PREFIX = "consumed:";

/** Strict Mode remounts the first composer in the same tick. New chat does not. */
export const LANDING_STARTER_RUNTIME_FALLBACK_MS = 2000;

let appliedStarterThisRuntime: LandingStarter | null = null;
let appliedStarterAtMs = 0;

function readSessionStarterState(): {
  pending: LandingStarter | null;
  consumed: LandingStarter | null;
} {
  const raw = readSessionStored(LANDING_STARTER_STORAGE_KEY);
  if (!raw) return { pending: null, consumed: null };
  if (raw.startsWith(STARTER_CONSUMED_PREFIX)) {
    return {
      pending: null,
      consumed:
        sanitizeLandingStarter(raw.slice(STARTER_CONSUMED_PREFIX.length)) ?? null,
    };
  }
  return { pending: sanitizeLandingStarter(raw) ?? null, consumed: null };
}

export function captureLandingIntent(
  search: string | URLSearchParams,
  landingPath?: string,
): LandingIntent | null {
  const incoming = parseLandingIntent(search, landingPath);
  if (incoming.starter) {
    const { consumed } = readSessionStarterState();
    if (consumed !== incoming.starter) {
      writeSessionStored(LANDING_STARTER_STORAGE_KEY, incoming.starter);
    }
  }
  const merged = mergeFirstTouchLandingIntent(readLandingIntent(), incoming);
  if (isEmptyLandingIntent(merged)) return null;
  writeStored(LANDING_INTENT_STORAGE_KEY, JSON.stringify(merged));
  return merged;
}

export function captureLandingIntentFromLocation(): LandingIntent | null {
  if (typeof window === "undefined") return null;
  return captureLandingIntent(window.location.search, window.location.pathname);
}

export function attributionPayload(
  intent: LandingIntent | null = readLandingIntent(),
): AttributionPayload | undefined {
  if (!intent || isEmptyLandingIntent(intent)) return undefined;
  const payload: AttributionPayload = {};
  for (const field of ATTRIBUTION_FIELDS) {
    const value = intent[field];
    if (value) payload[field] = value;
  }
  return isEmptyLandingIntent(payload) ? undefined : payload;
}

export function attributionBody(): { attribution?: AttributionPayload } {
  const attribution = attributionPayload();
  return attribution ? { attribution } : {};
}

export function hasCampaignAttribution(
  intent: LandingIntent | null = readLandingIntent(),
): boolean {
  if (!intent) return false;
  return Boolean(
    intent.utm_source ||
      intent.utm_medium ||
      intent.utm_campaign ||
      intent.utm_content ||
      intent.fbclid ||
      intent.ref ||
      intent.starter,
  );
}

export function takeLandingStarterPrefill(): LandingStarter | null {
  const { pending, consumed } = readSessionStarterState();
  if (pending) {
    writeSessionStored(
      LANDING_STARTER_STORAGE_KEY,
      `${STARTER_CONSUMED_PREFIX}${pending}`,
    );
    appliedStarterThisRuntime = pending;
    appliedStarterAtMs = Date.now();
    return pending;
  }
  if (!consumed) {
    removeSessionStored(LANDING_STARTER_STORAGE_KEY);
  }
  return null;
}

export function landingStarterAppliedThisRuntime(): LandingStarter | null {
  if (!appliedStarterThisRuntime) return null;
  if (Date.now() - appliedStarterAtMs > LANDING_STARTER_RUNTIME_FALLBACK_MS) {
    appliedStarterThisRuntime = null;
    appliedStarterAtMs = 0;
    return null;
  }
  return appliedStarterThisRuntime;
}

export function resetLandingStarterRuntime(): void {
  appliedStarterThisRuntime = null;
  appliedStarterAtMs = 0;
}

export function stripLandingStarterFromLocation(): void {
  if (typeof window === "undefined") return;
  const params = new URLSearchParams(window.location.search);
  if (!params.has("starter")) return;
  params.delete("starter");
  const query = params.toString();
  const next = `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash ?? ""}`;
  window.history.replaceState(null, "", next);
}

export function landingStarterCopyKey(
  starter: LandingStarter,
): (typeof LANDING_STARTER_COPY_KEYS)[LandingStarter] {
  return LANDING_STARTER_COPY_KEYS[starter];
}

export function pathWithSearch(pathname: string, search: string): string {
  const params = new URLSearchParams(
    search.startsWith("?") ? search.slice(1) : search,
  );
  if (pathname === "/chat") params.delete("auth");
  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}

export function currentChatPath(): string {
  return pathWithSearch(
    "/chat",
    typeof window === "undefined" ? "" : window.location.search,
  );
}

export function currentAuthLoginPath(): string {
  return authLoginPathFromSearch(
    typeof window === "undefined" ? "" : window.location.search,
  );
}

type SearchRecord = Record<string, string | string[] | undefined>;

export function authLoginPathFromSearch(
  search: URLSearchParams | SearchRecord | string,
): string {
  const params = new URLSearchParams();
  if (search instanceof URLSearchParams) {
    search.forEach((value, key) => {
      if (value) params.set(key, value);
    });
  } else if (typeof search === "string") {
    new URLSearchParams(search.startsWith("?") ? search.slice(1) : search).forEach(
      (value, key) => {
        if (value) params.set(key, value);
      },
    );
  } else {
    for (const [key, value] of Object.entries(search)) {
      const scalar = Array.isArray(value) ? value[0] : value;
      if (typeof scalar === "string" && scalar) params.set(key, scalar);
    }
  }
  params.set("auth", "login");
  return `/?${params.toString()}`;
}
