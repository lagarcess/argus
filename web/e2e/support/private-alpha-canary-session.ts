import { chmod, readFile, writeFile } from "node:fs/promises";

import { createServerClient } from "@supabase/ssr";
import { createClient, type Session, type User } from "@supabase/supabase-js";

type CookieOptions = {
  httpOnly?: boolean;
  maxAge?: number;
  path?: string;
  sameSite?: boolean | "lax" | "strict" | "none";
  secure?: boolean;
};

type PendingCookie = {
  name: string;
  value: string;
  options: CookieOptions;
};

type SessionHandoff = {
  schema_version: 1;
  access_token: string;
  refresh_token: string;
  expires_at: number;
  user_id: string;
  email: string;
};

const CANARY_PROVISIONING_EMAIL =
  /^private-alpha-canary\+[a-f0-9]{32}@get-argus\.com$/;

function requiredEnv(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`missing_${name.toLowerCase()}`);
  return value;
}

function serviceClient() {
  const supabaseUrl = requiredEnv("ARGUS_CANARY_SUPABASE_URL");
  const serviceRoleKey = requiredEnv(
    "ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY",
  );
  return createClient(supabaseUrl, serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      detectSessionInUrl: false,
      persistSession: false,
    },
  });
}

function normalizedSameSite(
  value: CookieOptions["sameSite"],
): "Lax" | "None" | "Strict" {
  if (value === "none") return "None";
  if (value === "strict") return "Strict";
  return "Lax";
}

function assertLeastPrivilegeUser(user: User, expectedEmail: string): void {
  const actualEmail = user.email?.trim().toLocaleLowerCase();
  const userRole = user.role?.trim().toLocaleLowerCase();
  const metadataRole = String(user.app_metadata?.role ?? "")
    .trim()
    .toLocaleLowerCase();
  if (
    actualEmail !== expectedEmail ||
    userRole !== "authenticated" ||
    user.is_anonymous === true ||
    ["admin", "developer", "service_role"].includes(metadataRole)
  ) {
    throw new Error("canary_identity_is_not_least_privilege");
  }
}

function assertLeastPrivilege(session: Session, expectedEmail: string): void {
  assertLeastPrivilegeUser(session.user, expectedEmail);
}

async function assertAllowlistedUser(email: string): Promise<void> {
  const client = serviceClient();
  const { data, error } = await client
    .from("private_alpha_allowlist")
    .select("email,role,disabled_at")
    .eq("email", email);
  if (error) throw new Error("canary_allowlist_lookup_failed");
  const rows = Array.isArray(data) ? data : [];
  const row = rows[0];
  if (
    rows.length !== 1 ||
    row?.email?.trim().toLocaleLowerCase() !== email ||
    row.role !== "user" ||
    row.disabled_at !== null
  ) {
    throw new Error("canary_identity_is_not_allowlisted_user");
  }
}

async function assertNonAdminProfile(userId: string): Promise<void> {
  const client = serviceClient();
  const { data, error } = await client
    .from("profiles")
    .select("id,is_admin")
    .eq("id", userId);
  const rows = Array.isArray(data) ? data : [];
  const row = rows[0];
  if (
    error ||
    rows.length !== 1 ||
    row?.id !== userId ||
    row.is_admin !== false
  ) {
    throw new Error("canary_identity_profile_is_not_least_privilege");
  }
}

async function assertProvisionableAllowlist(email: string): Promise<void> {
  const client = serviceClient();
  const { data, error } = await client
    .from("private_alpha_allowlist")
    .select("email,role,disabled_at")
    .eq("email", email);
  const rows = Array.isArray(data) ? data : [];
  if (error || rows.length > 1) {
    throw new Error("canary_allowlist_lookup_failed");
  }
  if (rows[0] && rows[0].role !== "user") {
    throw new Error("canary_existing_allowlist_is_not_least_privilege");
  }
}

async function usersMatchingEmail(email: string): Promise<User[]> {
  const client = serviceClient();
  const matches: User[] = [];
  for (let page = 1; page <= 1000; page += 1) {
    const { data, error } = await client.auth.admin.listUsers({
      page,
      perPage: 1000,
    });
    if (error) throw new Error("canary_identity_lookup_failed");
    const users = data.users as User[];
    matches.push(
      ...users.filter(
        (user) => user.email?.trim().toLocaleLowerCase() === email,
      ),
    );
    if (users.length < 1000) return matches;
  }
  throw new Error("canary_identity_lookup_unbounded");
}

function assertDedicatedUser(user: User | undefined, count: number): void {
  const source = String(user?.app_metadata?.source ?? "")
    .trim()
    .toLocaleLowerCase();
  if (
    count !== 1 ||
    source !== "private-alpha-canary" ||
    user?.is_anonymous === true
  ) {
    throw new Error("canary_identity_is_not_dedicated");
  }
}

async function assertDedicatedCanaryIdentity(email: string): Promise<User> {
  const matches = await usersMatchingEmail(email);
  const user = matches[0];
  assertDedicatedUser(user, matches.length);
  if (!user) throw new Error("canary_identity_is_not_dedicated");
  return user;
}

async function provision(): Promise<void> {
  const email = requiredEnv("ARGUS_CANARY_EMAIL").toLocaleLowerCase();
  if (!CANARY_PROVISIONING_EMAIL.test(email)) {
    throw new Error("canary_provisioning_email_is_not_safe");
  }

  await assertProvisionableAllowlist(email);
  const admin = serviceClient();
  const matches = await usersMatchingEmail(email);
  if (matches.length > 1) throw new Error("canary_identity_is_not_unique");
  let user = matches[0];
  let created = false;
  if (!user) {
    const { data, error } = await admin.auth.admin.createUser({
      email,
      email_confirm: true,
      app_metadata: { source: "private-alpha-canary" },
      user_metadata: { language: "es-419" },
    });
    if (error || !data.user) {
      throw new Error("canary_identity_provision_failed");
    }
    user = data.user;
    created = true;
  }

  try {
    assertDedicatedUser(user, 1);
    assertLeastPrivilegeUser(user, email);
    await assertNonAdminProfile(user.id);
    const client = serviceClient();
    const { data, error } = await client
      .from("private_alpha_allowlist")
      .upsert(
        {
          email,
          role: "user",
          language: "es-419",
          disabled_at: null,
        },
        { onConflict: "email" },
      )
      .select("email,role,disabled_at");
    const rows = Array.isArray(data) ? data : [];
    if (
      error ||
      rows.length !== 1 ||
      rows[0]?.email?.trim().toLocaleLowerCase() !== email ||
      rows[0]?.role !== "user" ||
      rows[0]?.disabled_at !== null
    ) {
      throw new Error("canary_allowlist_provision_failed");
    }
  } catch (error) {
    if (created) {
      const { error: rollbackError } = await admin.auth.admin.deleteUser(user.id);
      if (rollbackError) throw new Error("canary_identity_provision_rollback_failed");
    }
    throw error;
  }
  console.log("canary_identity_provision=ready");
}

async function storageStateCookies(
  session: Session,
): Promise<PendingCookie[]> {
  const pending = new Map<string, PendingCookie>();
  const client = createServerClient(
    requiredEnv("ARGUS_CANARY_SUPABASE_URL"),
    requiredEnv("ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY"),
    {
      auth: {
        autoRefreshToken: false,
        detectSessionInUrl: false,
        persistSession: true,
      },
      cookies: {
        getAll: () => [],
        setAll: (cookies) => {
          for (const cookie of cookies) {
            pending.set(cookie.name, cookie as PendingCookie);
          }
        },
      },
    },
  );
  const { data, error } = await client.auth.setSession({
    access_token: session.access_token,
    refresh_token: session.refresh_token,
  });
  if (error || data.user?.id !== session.user.id || pending.size === 0) {
    throw new Error("canary_storage_state_serialization_failed");
  }
  return [...pending.values()].filter((cookie) => cookie.value);
}

async function revokeTokens(accessToken: string): Promise<void> {
  const response = await fetch(
    `${requiredEnv("ARGUS_CANARY_SUPABASE_URL").replace(/\/$/, "")}/auth/v1/logout?scope=local`,
    {
      method: "POST",
      headers: {
        apikey: requiredEnv("ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY"),
        Authorization: `Bearer ${accessToken}`,
      },
    },
  );
  if (!response.ok) throw new Error("canary_session_revocation_failed");
}

async function mint(): Promise<void> {
  const email = requiredEnv("ARGUS_CANARY_EMAIL").toLocaleLowerCase();
  const storagePath = requiredEnv("ARGUS_CANARY_BROWSER_STORAGE_STATE");
  const sessionPath = requiredEnv("ARGUS_CANARY_BROWSER_SESSION_HANDOFF");
  const appUrl = new URL(requiredEnv("ARGUS_CANARY_APP_URL"));
  const dedicatedUser = await assertDedicatedCanaryIdentity(email);
  await Promise.all([
    assertAllowlistedUser(email),
    assertNonAdminProfile(dedicatedUser.id),
  ]);

  const admin = serviceClient();
  const { data: linkData, error: linkError } =
    await admin.auth.admin.generateLink({ type: "magiclink", email });
  const tokenHash = linkData?.properties?.hashed_token?.trim();
  const verificationType = linkData?.properties?.verification_type;
  if (linkError || !tokenHash || verificationType !== "magiclink") {
    throw new Error("canary_session_link_failed");
  }

  const verifier = serviceClient();
  const { data, error } = await verifier.auth.verifyOtp({
    token_hash: tokenHash,
    type: "magiclink",
  });
  if (error || !data.session) throw new Error("canary_session_mint_failed");

  try {
    assertLeastPrivilege(data.session, email);
    await assertNonAdminProfile(data.session.user.id);
    const cookies = await storageStateCookies(data.session);
    const now = Math.floor(Date.now() / 1000);
    const storageState = {
      cookies: cookies.map(({ name, value, options }) => ({
        name,
        value,
        domain: appUrl.hostname,
        path: options.path ?? "/",
        expires:
          typeof options.maxAge === "number" && options.maxAge > 0
            ? now + options.maxAge
            : -1,
        httpOnly: options.httpOnly ?? false,
        secure: options.secure ?? appUrl.protocol === "https:",
        sameSite: normalizedSameSite(options.sameSite),
      })),
      origins: [],
    };
    const handoff: SessionHandoff = {
      schema_version: 1,
      access_token: data.session.access_token,
      refresh_token: data.session.refresh_token,
      expires_at: data.session.expires_at ?? 0,
      user_id: data.session.user.id,
      email,
    };
    await writeFile(storagePath, `${JSON.stringify(storageState)}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
    await writeFile(sessionPath, `${JSON.stringify(handoff)}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
    await Promise.all([chmod(storagePath, 0o600), chmod(sessionPath, 0o600)]);
  } catch (error) {
    await revokeTokens(data.session.access_token).catch(() => undefined);
    throw error;
  }
  console.log("canary_session_state=ready");
}

function sessionHandoff(value: unknown): SessionHandoff {
  const handoff = value as Partial<SessionHandoff>;
  if (
    handoff?.schema_version !== 1 ||
    typeof handoff.access_token !== "string" ||
    typeof handoff.refresh_token !== "string" ||
    typeof handoff.user_id !== "string" ||
    typeof handoff.email !== "string"
  ) {
    throw new Error("canary_session_handoff_invalid");
  }
  return handoff as SessionHandoff;
}

async function revoke(): Promise<void> {
  const sessionPath = requiredEnv("ARGUS_CANARY_BROWSER_SESSION_HANDOFF");
  const handoff = sessionHandoff(
    JSON.parse(await readFile(sessionPath, "utf8")) as unknown,
  );
  await revokeTokens(handoff.access_token);
  console.log("canary_session_revocation=completed");
}

async function main(): Promise<void> {
  const mode = process.argv[2];
  if (mode === "provision") {
    await provision();
    return;
  }
  if (mode === "mint") {
    await mint();
    return;
  }
  if (mode === "revoke") {
    await revoke();
    return;
  }
  throw new Error("canary_session_mode_invalid");
}

main().catch((error: unknown) => {
  const reason = error instanceof Error ? error.message : "unknown_failure";
  console.error(`canary_session_state=failed reason=${reason}`);
  process.exitCode = 1;
});
