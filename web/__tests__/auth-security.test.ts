import { describe, expect, test } from "bun:test";

import {
  createAuthSecurityActions,
  type AuthSecurityPort,
} from "../lib/auth-security";
import { synchronizeCurrentBrowserLogout } from "../lib/argus-api";
import {
  handleRecoveryRequest,
  RecoveryAttemptLimiter,
  recoveryRedirectTarget,
} from "../lib/recovery-request";

function authPort(options?: {
  exchangeError?: Error;
  updateError?: Error;
  signOutError?: Error;
}) {
  const exchangedCodes: string[] = [];
  const updates: Array<Record<string, string>> = [];
  const scopes: string[] = [];
  const auth: AuthSecurityPort = {
    async exchangeCodeForSession(code) {
      exchangedCodes.push(code);
      return { error: options?.exchangeError ?? null };
    },
    async updateUser(attributes) {
      updates.push(attributes);
      return { error: options?.updateError ?? null };
    },
    async signOut({ scope }) {
      scopes.push(scope);
      return { error: options?.signOutError ?? null };
    },
  };
  return { auth, exchangedCodes, updates, scopes };
}

describe("account security actions", () => {
  test("ordinary logout clears Argus cookies even when local revocation fails", async () => {
    const scopes: string[] = [];
    let cookieClears = 0;

    expect(
      synchronizeCurrentBrowserLogout(
        {
          async signOut({ scope }) {
            scopes.push(scope);
            return { error: new Error("provider unavailable") };
          },
        },
        async () => {
          cookieClears += 1;
          return { success: true };
        },
      ),
    ).rejects.toThrow();

    expect(scopes).toEqual(["local"]);
    expect(cookieClears).toBe(1);
  });

  test("normal password change proves the current password and requires a fresh login", async () => {
    const port = authPort();
    let cookieClears = 0;
    const actions = createAuthSecurityActions(port.auth, async () => {
      cookieClears += 1;
    });

    const result = await actions.changePassword({
      currentPassword: "old-password",
      newPassword: "new-password",
    });

    expect(port.updates).toEqual([
      { password: "new-password", current_password: "old-password" },
    ]);
    expect(port.scopes).toEqual(["global"]);
    expect(cookieClears).toBe(1);
    expect(result).toEqual({
      currentSessionPreserved: false,
      freshLoginRequired: true,
      cookieSync: "cleared",
    });
  });

  test("recovery exchanges one code before changing the password", async () => {
    const port = authPort();
    const actions = createAuthSecurityActions(port.auth, async () => undefined);

    await actions.exchangeRecoveryCode("one-time-code");
    const result = await actions.resetRecoveredPassword("new-password");

    expect(port.exchangedCodes).toEqual(["one-time-code"]);
    expect(port.updates).toEqual([{ password: "new-password" }]);
    expect(port.scopes).toEqual(["global"]);
    expect(result.freshLoginRequired).toBe(true);
  });

  test("an invalid or reused recovery code cannot change a password", async () => {
    const port = authPort({ exchangeError: new Error("expired") });
    const actions = createAuthSecurityActions(port.auth, async () => undefined);

    expect(actions.exchangeRecoveryCode("reused-code")).rejects.toThrow();
    expect(port.updates).toEqual([]);
    expect(port.scopes).toEqual([]);
  });

  test("signing out other sessions preserves this browser and its cookies", async () => {
    const port = authPort();
    let cookieClears = 0;
    const actions = createAuthSecurityActions(port.auth, async () => {
      cookieClears += 1;
    });

    const result = await actions.signOutOtherSessions();

    expect(port.scopes).toEqual(["others"]);
    expect(cookieClears).toBe(0);
    expect(result).toEqual({
      currentSessionPreserved: true,
      freshLoginRequired: false,
      cookieSync: "not_required",
    });
  });

  test("signing out this browser uses only the local scope", async () => {
    const port = authPort();
    let cookieClears = 0;
    const actions = createAuthSecurityActions(port.auth, async () => {
      cookieClears += 1;
    });

    const result = await actions.signOutThisBrowser();

    expect(port.scopes).toEqual(["local"]);
    expect(cookieClears).toBe(1);
    expect(result.freshLoginRequired).toBe(true);
  });

  test("a revoke-others provider failure does not claim success", async () => {
    const port = authPort({ signOutError: new Error("backend unavailable") });
    let cookieClears = 0;
    const actions = createAuthSecurityActions(port.auth, async () => {
      cookieClears += 1;
    });

    expect(actions.signOutOtherSessions()).rejects.toThrow();
    expect(port.scopes).toEqual(["others"]);
    expect(cookieClears).toBe(0);
  });

  test("global sign out reports partial cleanup without claiming cookie sync", async () => {
    const port = authPort();
    const actions = createAuthSecurityActions(port.auth, async () => {
      throw new Error("backend unavailable");
    });

    const result = await actions.signOutAllSessions();

    expect(port.scopes).toEqual(["global"]);
    expect(result).toEqual({
      currentSessionPreserved: false,
      freshLoginRequired: true,
      cookieSync: "failed",
    });
  });
});

describe("recovery request safety", () => {
  test("production recovery uses one configured origin and rejects another", () => {
    expect(
      recoveryRedirectTarget({
        requestUrl: "https://app.argus.example/api/auth/recovery",
        requestOrigin: "https://app.argus.example",
        configuredAppOrigin: "https://app.argus.example",
        environment: "production",
      }),
    ).toBe("https://app.argus.example/auth/recovery");
    expect(
      recoveryRedirectTarget({
        requestUrl: "https://app.argus.example/api/auth/recovery",
        requestOrigin: "https://attacker.example",
        configuredAppOrigin: "https://app.argus.example",
        environment: "production",
      }),
    ).toBeNull();
  });

  test("local recovery allows only the documented local origins", () => {
    expect(
      recoveryRedirectTarget({
        requestUrl: "http://localhost:3000/api/auth/recovery",
        requestOrigin: "http://localhost:3000",
        configuredAppOrigin: undefined,
        environment: "development",
      }),
    ).toBe("http://localhost:3000/auth/recovery");
    expect(
      recoveryRedirectTarget({
        requestUrl: "http://evil.local:3000/api/auth/recovery",
        requestOrigin: "http://evil.local:3000",
        configuredAppOrigin: undefined,
        environment: "development",
      }),
    ).toBeNull();
  });

  test("rate limiting applies independently to normalized email and address", () => {
    let now = 1_000;
    const limiter = new RecoveryAttemptLimiter({
      limit: 2,
      windowMs: 1_000,
      now: () => now,
    });

    expect(limiter.retryAfterMs(["email:user@example.com", "ip:127.0.0.1"])).toBe(0);
    expect(limiter.retryAfterMs(["email:user@example.com", "ip:127.0.0.2"])).toBe(0);
    expect(limiter.retryAfterMs(["email:user@example.com", "ip:127.0.0.3"])).toBe(1_000);
    now = 2_001;
    expect(limiter.retryAfterMs(["email:user@example.com", "ip:127.0.0.3"])).toBe(0);
  });

  test("provider success and failure return the same enumeration-safe response", async () => {
    const request = () =>
      new Request("https://app.argus.example/api/auth/recovery", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: "https://app.argus.example",
        },
        body: JSON.stringify({ email: "person@example.com" }),
      });
    const dependencies = (sendRecovery: (email: string, redirectTo: string) => Promise<void>) => ({
      configuredAppOrigin: "https://app.argus.example",
      environment: "production",
      limiter: new RecoveryAttemptLimiter({ limit: 5, windowMs: 60_000 }),
      sendRecovery,
    });

    const accepted = await handleRecoveryRequest(
      request(),
      dependencies(async () => undefined),
    );
    const rejected = await handleRecoveryRequest(
      request(),
      dependencies(async () => {
        throw new Error("account missing");
      }),
    );

    expect(accepted.status).toBe(202);
    expect(rejected.status).toBe(202);
    expect(await accepted.json()).toEqual(await rejected.json());
  });

  test("recovery ignores a body-supplied redirect", async () => {
    let destination = "";
    const response = await handleRecoveryRequest(
      new Request("https://app.argus.example/api/auth/recovery", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: "https://app.argus.example",
        },
        body: JSON.stringify({
          email: "person@example.com",
          redirectTo: "https://attacker.example/steal",
        }),
      }),
      {
        configuredAppOrigin: "https://app.argus.example",
        environment: "production",
        limiter: new RecoveryAttemptLimiter({ limit: 5, windowMs: 60_000 }),
        async sendRecovery(_email, redirectTo) {
          destination = redirectTo;
        },
      },
    );

    expect(response.status).toBe(202);
    expect(destination).toBe("https://app.argus.example/auth/recovery");
  });
});
