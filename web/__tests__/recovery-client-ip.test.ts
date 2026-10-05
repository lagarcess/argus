import { expect, test } from "bun:test";
import { handleRecoveryRequest, RecoveryAttemptLimiter } from "../lib/recovery-request";

const attemptLimit = 5;
const globalLimit = 100;
const windowMs = 600_000;
const origin = "https://example.test";

function fixture(trustedClientIpHeader?: string) {
  let sends = 0;
  const dependencies = {
    configuredAppOrigin: origin, environment: "production", trustedClientIpHeader,
    limiter: new RecoveryAttemptLimiter({ limit: attemptLimit, windowMs }),
    globalLimiter: new RecoveryAttemptLimiter({ limit: globalLimit, windowMs }),
    async sendRecovery() { sends += 1; },
  };
  return {
    get sends() { return sends; },
    async request(index: number, headers: Record<string, string>, email = `synthetic${index}@example.test`) {
      return handleRecoveryRequest(new Request(`${origin}/api/auth/recovery`, {
        method: "POST", headers: { "Content-Type": "application/json", Origin: origin, ...headers },
        body: JSON.stringify({ email, captcha_token: "synthetic-captcha" }),
      }), dependencies);
    },
  };
}

for (const setting of [undefined, "", "   ", " X-Verified-Client-IP "]) {
  test(`trusted address survives rotated forwarding headers: ${JSON.stringify(setting)}`, async () => {
    const f = fixture(setting);
    for (let i = 0; i <= attemptLimit; i += 1) {
      const response = await f.request(i, {
        "CF-Connecting-IP": `192.0.2.${i + 1}`,
        "X-Forwarded-For": `198.51.100.${i + 1}, 192.0.2.1`,
        "X-Real-IP": `198.51.100.${i + 1}`,
        [setting?.trim() || "CF-Connecting-IP"]: "203.0.113.55",
      });
      expect(response.status).toBe(i < attemptLimit ? 202 : 429);
      if (i === attemptLimit) expect(Number(response.headers.get("Retry-After"))).toBeGreaterThan(0);
    }
    expect(f.sends).toBe(attemptLimit);
  });
}

for (const setting of [undefined, "X-Verified-Client-IP"]) {
  test(`missing selected header shares the unknown bucket: ${setting}`, async () => {
    const f = fixture(setting);
    for (let i = 0; i <= attemptLimit; i += 1) {
      const response = await f.request(i, {
        "X-Forwarded-For": `198.51.100.${i + 1}`, "X-Real-IP": `192.0.2.${i + 1}`,
        ...(setting ? { "CF-Connecting-IP": `203.0.113.${i + 1}` } : {}),
      });
      expect(response.status).toBe(i < attemptLimit ? 202 : 429);
    }
    expect(f.sends).toBe(attemptLimit);
  });
}

for (const address of ["not-an-ip", "1".repeat(46), "203.0.113.55, 198.51.100.1"]) {
  test(`invalid trusted address rejects before sending: ${address}`, async () => {
    const f = fixture();
    const response = await f.request(0, { "CF-Connecting-IP": address, "X-Forwarded-For": "192.0.2.1" });
    expect(response.status).toBe(400);
    expect(f.sends).toBe(0);
  });
}

test("same email remains bounded across trusted addresses", async () => {
  const f = fixture();
  for (let i = 0; i <= attemptLimit; i += 1) {
    const response = await f.request(i, { "CF-Connecting-IP": `203.0.113.${i + 1}` }, "same@example.test");
    expect(response.status).toBe(i < attemptLimit ? 202 : 429);
  }
  expect(f.sends).toBe(attemptLimit);
});

test("global budget bounds distinct trusted addresses and emails", async () => {
  const f = fixture();
  for (let i = 0; i <= globalLimit; i += 1) {
    const response = await f.request(i, { "CF-Connecting-IP": `203.0.113.${i + 1}` });
    expect(response.status).toBe(i < globalLimit ? 202 : 429);
  }
  expect(f.sends).toBe(globalLimit);
});
