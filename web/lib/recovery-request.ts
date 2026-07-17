const LOCAL_RECOVERY_ORIGINS = new Set([
  "http://localhost:3000",
  "http://127.0.0.1:3000",
  "http://localhost:3001",
  "http://127.0.0.1:3001",
]);
const MAX_TRACKED_RECOVERY_KEYS = 2_048;

function exactOrigin(value: string | undefined): string | null {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    if (parsed.pathname !== "/" || parsed.search || parsed.hash) return null;
    return parsed.origin;
  } catch {
    return null;
  }
}

export function recoveryRedirectTarget({
  requestUrl,
  requestOrigin,
  configuredAppOrigin,
  environment,
}: {
  requestUrl: string;
  requestOrigin: string | null;
  configuredAppOrigin: string | undefined;
  environment: string | undefined;
}): string | null {
  const requestUrlOrigin = exactOrigin(new URL(requestUrl).origin);
  const browserOrigin = requestOrigin ? exactOrigin(requestOrigin) : null;
  const configuredOrigin = exactOrigin(configuredAppOrigin);
  const isDevelopment = environment !== "production";
  const allowedOrigins = new Set<string>();
  if (configuredOrigin) allowedOrigins.add(configuredOrigin);
  if (isDevelopment) {
    LOCAL_RECOVERY_ORIGINS.forEach((origin) => allowedOrigins.add(origin));
  }
  if (browserOrigin && !allowedOrigins.has(browserOrigin)) return null;

  const redirectOrigin =
    configuredOrigin ??
    (requestUrlOrigin && LOCAL_RECOVERY_ORIGINS.has(requestUrlOrigin)
      ? requestUrlOrigin
      : null);
  return redirectOrigin ? `${redirectOrigin}/auth/recovery` : null;
}

export class RecoveryAttemptLimiter {
  private readonly attempts = new Map<string, number[]>();

  constructor(
    private readonly options: {
      limit: number;
      windowMs: number;
      now?: () => number;
    },
  ) {}

  private compact(now: number): void {
    for (const [key, attempts] of this.attempts.entries()) {
      const recent = attempts.filter(
        (attempt) => now - attempt < this.options.windowMs,
      );
      if (recent.length === 0) {
        this.attempts.delete(key);
      } else if (recent.length !== attempts.length) {
        this.attempts.set(key, recent);
      }
    }
  }

  private enforceCapacity(): void {
    while (this.attempts.size > MAX_TRACKED_RECOVERY_KEYS) {
      const oldestKey = this.attempts.keys().next().value;
      if (oldestKey === undefined) return;
      this.attempts.delete(oldestKey);
    }
  }

  retryAfterMs(keys: string[]): number {
    const now = this.options.now?.() ?? Date.now();
    this.compact(now);
    const recentByKey = keys.map((key) => {
      const recent = this.attempts.get(key) ?? [];
      return { key, recent };
    });
    const retryAfter = recentByKey.reduce((longest, { recent }) => {
      if (recent.length < this.options.limit) return longest;
      return Math.max(longest, this.options.windowMs - (now - recent[0]));
    }, 0);
    if (retryAfter > 0) return retryAfter;
    recentByKey.forEach(({ key, recent }) => {
      // Reinsertion makes the bounded map evict the least-recently-used keys.
      this.attempts.delete(key);
      this.attempts.set(key, [...recent, now]);
    });
    this.enforceCapacity();
    return 0;
  }
}

type RecoveryRequestDependencies = {
  configuredAppOrigin: string | undefined;
  environment: string | undefined;
  limiter: RecoveryAttemptLimiter;
  sendRecovery: (email: string, redirectTo: string) => Promise<void>;
};

const noStoreHeaders = {
  "Cache-Control": "no-store",
  "Content-Type": "application/json",
};

function jsonResponse(
  body: { accepted: boolean },
  status: number,
  headers?: Record<string, string>,
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...noStoreHeaders, ...headers },
  });
}

function clientAddress(request: Request): string {
  return (
    request.headers.get("x-forwarded-for")?.split(",", 1)[0]?.trim() ||
    request.headers.get("x-real-ip")?.trim() ||
    "unknown"
  );
}

export async function handleRecoveryRequest(
  request: Request,
  dependencies: RecoveryRequestDependencies,
): Promise<Response> {
  if (
    dependencies.environment === "production" &&
    !exactOrigin(dependencies.configuredAppOrigin)
  ) {
    return jsonResponse({ accepted: false }, 503);
  }
  const requestOrigin = request.headers.get("origin");
  const redirectTo = recoveryRedirectTarget({
    requestUrl: request.url,
    requestOrigin,
    configuredAppOrigin: dependencies.configuredAppOrigin,
    environment: dependencies.environment,
  });
  if (!redirectTo) {
    return jsonResponse({ accepted: false }, requestOrigin ? 403 : 503);
  }

  let body: { email?: unknown };
  try {
    body = (await request.json()) as { email?: unknown };
  } catch {
    return jsonResponse({ accepted: false }, 400);
  }
  const email =
    typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
  if (!/^\S+@\S+\.\S+$/.test(email)) {
    return jsonResponse({ accepted: true }, 202);
  }

  const retryAfterMs = dependencies.limiter.retryAfterMs([
    `email:${email}`,
    `ip:${clientAddress(request)}`,
  ]);
  if (retryAfterMs > 0) {
    return jsonResponse({ accepted: false }, 429, {
      "Retry-After": String(Math.max(1, Math.ceil(retryAfterMs / 1_000))),
    });
  }

  try {
    await dependencies.sendRecovery(email, redirectTo);
  } catch {
    // Account existence and provider state never change the public response.
  }
  return jsonResponse({ accepted: true }, 202);
}
