import { businessContactEmail } from "../../components/site-copy";
import { PROVIDER_TIMEOUT_MS, type FormsConfig } from "../forms/config";
import { SIGNUP_TABLE } from "../forms/signup";
import { emailDigest, normalizeEmail } from "../forms/validation";
import type { BusinessLocale } from "../site-routes";

// Operator-side signup handling. The marketing service only ever inserts; every
// read, removal and notification goes through these functions so a removed
// address can never be selected for a message.

export type ActiveSignup = {
  email_digest: string;
  email: string;
  language: BusinessLocale;
};

export type NoticeTemplate = {
  id: string;
  subject: Record<BusinessLocale, string>;
  text: Record<BusinessLocale, string>;
};

type OpsConfig = FormsConfig & { noticeFrom: string | null };

const PAGE = 500;

function restHeaders(config: OpsConfig, extra: Record<string, string> = {}): Record<string, string> {
  return {
    apikey: config.supabaseServiceKey ?? "",
    Authorization: `Bearer ${config.supabaseServiceKey}`,
    "Content-Type": "application/json",
    ...extra,
  };
}

function table(config: OpsConfig, query = ""): string {
  return `${config.supabaseUrl}/rest/v1/${SIGNUP_TABLE}${query}`;
}

async function checked(response: Response, action: string): Promise<Response> {
  if (!response.ok) throw new Error(`${action} failed with HTTP ${response.status}`);
  return response;
}

// Active and not yet told: the only rows a notice may reach.
export async function pendingSignups(config: OpsConfig, doFetch: typeof fetch): Promise<ActiveSignup[]> {
  const rows: ActiveSignup[] = [];
  for (let offset = 0; ; offset += PAGE) {
    const query = `?select=email_digest,email,language&removed_at=is.null&notified_at=is.null&order=created_at.asc,email_digest.asc&limit=${PAGE}&offset=${offset}`;
    const response = await checked(
      await doFetch(table(config, query), { headers: restHeaders(config), signal: AbortSignal.timeout(PROVIDER_TIMEOUT_MS) }),
      "reading signups",
    );
    const page = (await response.json()) as ActiveSignup[];
    rows.push(...page);
    if (page.length < PAGE) return rows;
  }
}

export async function signupCounts(config: OpsConfig, doFetch: typeof fetch) {
  const count = async (filter: string): Promise<number> => {
    const response = await checked(
      await doFetch(table(config, `?select=email_digest&${filter}`), {
        headers: restHeaders(config, { Prefer: "count=exact", Range: "0-0" }),
        signal: AbortSignal.timeout(PROVIDER_TIMEOUT_MS),
      }),
      "counting signups",
    );
    return Number(response.headers.get("content-range")?.split("/")[1] ?? 0);
  };
  return {
    active: await count("removed_at=is.null"),
    pending: await count("removed_at=is.null&notified_at=is.null"),
    removed: await count("removed_at=not.is.null"),
  };
}

// Erases the address and keeps the digest as the suppression record. An address
// that never registered still gets a suppression row, so a later signup from it
// is ignored too.
export async function removeSignup(
  config: OpsConfig,
  rawEmail: string,
  doFetch: typeof fetch,
  now: () => Date = () => new Date(),
): Promise<"removed" | "suppressed"> {
  const digest = emailDigest(normalizeEmail(rawEmail));
  const removedAt = now().toISOString();
  const updated = await checked(
    await doFetch(table(config, `?email_digest=eq.${digest}&removed_at=is.null`), {
      method: "PATCH",
      headers: restHeaders(config, { Prefer: "return=representation" }),
      body: JSON.stringify({ email: null, removed_at: removedAt }),
      signal: AbortSignal.timeout(PROVIDER_TIMEOUT_MS),
    }),
    "removing the signup",
  );
  if (((await updated.json()) as unknown[]).length > 0) return "removed";
  await checked(
    await doFetch(table(config, "?on_conflict=email_digest"), {
      method: "POST",
      headers: restHeaders(config, { Prefer: "resolution=ignore-duplicates,return=minimal" }),
      body: JSON.stringify({
        email_digest: digest,
        email: null,
        language: "es",
        consent_version: "removal-request",
        source: "operator-removal",
        removed_at: removedAt,
      }),
      signal: AbortSignal.timeout(PROVIDER_TIMEOUT_MS),
    }),
    "recording the suppression",
  );
  return "suppressed";
}

export function validateTemplate(template: NoticeTemplate): string[] {
  const problems: string[] = [];
  if (!template.id?.trim()) problems.push("id is required");
  for (const language of ["es", "en"] as const) {
    if (!template.subject?.[language]?.trim()) problems.push(`subject.${language} is required`);
    const text = template.text?.[language] ?? "";
    if (!text.trim()) problems.push(`text.${language} is required`);
    // Every notice must show how to leave the list.
    else if (!text.includes(businessContactEmail)) {
      problems.push(`text.${language} must mention ${businessContactEmail} so the reader can opt out`);
    }
  }
  return problems;
}

export type NoticePlan = {
  recipients: ActiveSignup[];
  stamp: boolean;
};

// --only restricts to named, approved test addresses. Those sends never stamp
// notified_at, so a test cannot use up a real signup's one notice.
export function planNotice(pending: ActiveSignup[], only: string[] | null): NoticePlan {
  if (!only) return { recipients: pending, stamp: true };
  const wanted = new Set(only.map(normalizeEmail));
  return { recipients: pending.filter((row) => wanted.has(row.email)), stamp: false };
}

export async function sendNotice(
  config: OpsConfig,
  template: NoticeTemplate,
  plan: NoticePlan,
  doFetch: typeof fetch,
  now: () => Date = () => new Date(),
): Promise<{ sent: number; failed: number; sentNotRecorded: string[]; stoppedEarly: boolean }> {
  let sent = 0;
  let failed = 0;
  const sentNotRecorded: string[] = [];
  let stoppedEarly = false;
  for (const row of plan.recipients) {
    const key = `${plan.stamp ? "notice" : "notice-test"}-${template.id}-${row.email_digest}`;
    try {
      const response = await doFetch(`${config.resendApiUrl}/emails`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${config.resendApiKey}`,
          "Content-Type": "application/json",
          "Idempotency-Key": key,
        },
        body: JSON.stringify({
          from: config.noticeFrom,
          to: [row.email],
          reply_to: businessContactEmail,
          subject: template.subject[row.language],
          text: template.text[row.language],
        }),
        signal: AbortSignal.timeout(PROVIDER_TIMEOUT_MS),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
    } catch {
      failed += 1;
      continue;
    }
    sent += 1;
    if (!plan.stamp) continue;
    // The message is out. A failed stamp is reported on its own, because
    // sending that row again after the idempotency window would double-send.
    try {
      await checked(
        await doFetch(table(config, `?email_digest=eq.${row.email_digest}&removed_at=is.null`), {
          method: "PATCH",
          headers: restHeaders(config, { Prefer: "return=minimal" }),
          body: JSON.stringify({ notified_at: now().toISOString() }),
          signal: AbortSignal.timeout(PROVIDER_TIMEOUT_MS),
        }),
        "recording the notice",
      );
    } catch {
      // The database stopped recording. Sending on would mail people it cannot
      // remember, so stop here and hand the operator exactly who was sent.
      sentNotRecorded.push(row.email_digest);
      stoppedEarly = true;
      break;
    }
  }
  return { sent, failed, sentNotRecorded, stoppedEarly };
}

export type { OpsConfig };
