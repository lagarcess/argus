import { describe, expect, test } from "bun:test";
import {
  planNotice,
  removeSignup,
  sendNotice,
  validateTemplate,
  type ActiveSignup,
  type NoticeTemplate,
  type OpsConfig,
} from "../lib/ops/signups";
import { emailDigest } from "../lib/forms/validation";
import { CONFIG, recordingFetch } from "./forms-support";

const ops: OpsConfig = { ...CONFIG, noticeFrom: "Cuadrao <news@notify.example.test>" };
const row = (email: string, language: "es" | "en" = "es"): ActiveSignup => ({
  email_digest: emailDigest(email),
  email,
  language,
});
const template: NoticeTemplate = {
  id: "availability-1",
  subject: { es: "Ya puedes probar Cuadrao", en: "You can try Cuadrao" },
  text: {
    es: "Hola. Para salir de la lista escribe a hola@cuadrao.ai.",
    en: "Hello. To leave the list write to hola@cuadrao.ai.",
  },
};

describe("removal", () => {
  test("erases the address of an active signup and keeps its digest", async () => {
    const { fetch: doFetch, calls } = recordingFetch(() => Response.json([{ email_digest: "x" }]));
    const result = await removeSignup(ops, " Ana@Example.INVALID ", doFetch, () => new Date("2026-10-08T00:00:00Z"));
    expect(result).toBe("removed");
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toContain(`email_digest=eq.${emailDigest("ana@example.invalid")}&removed_at=is.null`);
    expect(calls[0].init.method).toBe("PATCH");
    expect(JSON.parse(String(calls[0].init.body))).toEqual({
      email: null,
      removed_at: "2026-10-08T00:00:00.000Z",
    });
  });

  test("an address that never registered is recorded as suppressed", async () => {
    const { fetch: doFetch, calls } = recordingFetch((call) =>
      call.init.method === "PATCH" ? Response.json([]) : new Response(null, { status: 201 }),
    );
    expect(await removeSignup(ops, "ghost@example.invalid", doFetch)).toBe("suppressed");
    const body = JSON.parse(String(calls[1].init.body));
    expect(body.email).toBeNull();
    expect(body.email_digest).toBe(emailDigest("ghost@example.invalid"));
    expect(calls[1].init.headers).toMatchObject({ Prefer: "resolution=ignore-duplicates,return=minimal" });
  });

  test("a database error is raised, not reported as done", async () => {
    const { fetch: doFetch } = recordingFetch(() => new Response("", { status: 500 }));
    await expect(removeSignup(ops, "ana@example.invalid", doFetch)).rejects.toThrow("HTTP 500");
  });
});

describe("notice planning", () => {
  const pending = [row("a@example.invalid"), row("b@example.invalid", "en")];

  test("a full send reaches every pending signup and stamps them", () => {
    expect(planNotice(pending, null)).toEqual({ recipients: pending, stamp: true });
  });

  test("--only reaches only the named pending addresses and never stamps", () => {
    expect(planNotice(pending, [" B@Example.INVALID ", "stranger@example.invalid"])).toEqual({
      recipients: [pending[1]],
      stamp: false,
    });
  });
});

describe("notice template", () => {
  test("accepts a template that tells readers how to leave", () => {
    expect(validateTemplate(template)).toEqual([]);
  });

  test("rejects a notice without the opt-out address or a language", () => {
    const bad = { ...template, text: { es: "Hola", en: "" } };
    expect(validateTemplate(bad)).toEqual([
      "text.es must mention hola@cuadrao.ai so the reader can opt out",
      "text.en is required",
    ]);
  });
});

describe("notice sending", () => {
  test("sends in the signup's language with a per-recipient idempotency key and stamps it", async () => {
    const { fetch: doFetch, calls } = recordingFetch(() => Response.json({ id: "x" }));
    const plan = planNotice([row("a@example.invalid", "en")], null);
    const result = await sendNotice(ops, template, plan, doFetch, () => new Date("2026-10-09T00:00:00Z"));
    expect(result).toEqual({ sent: 1, failed: 0, sentNotRecorded: [], stoppedEarly: false });
    const email = JSON.parse(String(calls[0].init.body));
    expect(email.to).toEqual(["a@example.invalid"]);
    expect(email.subject).toBe("You can try Cuadrao");
    expect(email.reply_to).toBe("hola@cuadrao.ai");
    expect((calls[0].init.headers as Record<string, string>)["Idempotency-Key"]).toBe(
      `notice-availability-1-${emailDigest("a@example.invalid")}`,
    );
    expect(calls[1].init.method).toBe("PATCH");
    expect(JSON.parse(String(calls[1].init.body))).toEqual({ notified_at: "2026-10-09T00:00:00.000Z" });
  });

  test("a failed send is counted and is not stamped", async () => {
    const { fetch: doFetch, calls } = recordingFetch(() => new Response("", { status: 422 }));
    const result = await sendNotice(ops, template, planNotice([row("a@example.invalid")], null), doFetch);
    expect(result).toEqual({ sent: 0, failed: 1, sentNotRecorded: [], stoppedEarly: false });
    expect(calls).toHaveLength(1);
  });

  test("a sent message whose stamp fails is reported apart from a failed send", async () => {
    const { fetch: doFetch, calls } = recordingFetch((call) =>
      call.init.method === "PATCH" ? new Response("", { status: 500 }) : Response.json({ id: "x" }),
    );
    const result = await sendNotice(ops, template, planNotice([row("a@example.invalid")], null), doFetch);
    expect(result).toEqual({
      sent: 1,
      failed: 0,
      sentNotRecorded: [emailDigest("a@example.invalid")],
      stoppedEarly: true,
    });
    expect(calls).toHaveLength(2);
  });

  test("stops at the first unrecorded stamp instead of mailing the rest", async () => {
    const { fetch: doFetch, calls } = recordingFetch((call) =>
      call.init.method === "PATCH" ? new Response("", { status: 503 }) : Response.json({ id: "x" }),
    );
    const plan = planNotice(
      [row("a@example.invalid"), row("b@example.invalid"), row("c@example.invalid")],
      null,
    );
    const result = await sendNotice(ops, template, plan, doFetch);
    expect(result.sent).toBe(1);
    expect(result.sentNotRecorded).toEqual([emailDigest("a@example.invalid")]);
    expect(result.stoppedEarly).toBe(true);
    // one send and one failed stamp; b and c were never mailed
    expect(calls.map((call) => call.init.method)).toEqual(["POST", "PATCH"]);
  });

  test("the stamp only applies to a row that is still active", async () => {
    const { fetch: doFetch, calls } = recordingFetch(() => Response.json({ id: "x" }));
    await sendNotice(ops, template, planNotice([row("a@example.invalid")], null), doFetch);
    expect(calls[1].url).toContain("&removed_at=is.null");
  });

  test("a test send neither stamps nor shares an idempotency key with the real notice", async () => {
    const { fetch: doFetch, calls } = recordingFetch(() => Response.json({ id: "x" }));
    const plan = planNotice([row("a@example.invalid")], ["a@example.invalid"]);
    await sendNotice(ops, template, plan, doFetch);
    expect(calls).toHaveLength(1);
    expect((calls[0].init.headers as Record<string, string>)["Idempotency-Key"]).toStartWith("notice-test-");
  });
});
