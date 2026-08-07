import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  COOKIE_DISCLOSURE_RULES,
  UndisclosedCookieError,
  assertDisclosedCookie,
  disclosedCookieConcept,
} from "../lib/browser-cookies";
import en from "../public/locales/en/common.json";
import es419 from "../public/locales/es-419/common.json";

const REPO_ROOT = join(import.meta.dir, "..", "..");
const CATALOGS = { en, "es-419": es419 } as const;

/** The name @supabase/ssr derives, built the way the library builds it. */
function supabaseCookieName(projectUrl: string): string {
  return `sb-${new URL(projectUrl).hostname.split(".")[0]}-auth-token`;
}

function backendCookieRegistry(): Record<string, string> {
  const source = readFileSync(
    join(REPO_ROOT, "src", "argus", "api", "browser_cookies.py"),
    "utf-8",
  );
  const block = source.match(
    /COOKIE_REGISTRY:\s*Final\[dict\[str,\s*str\]\]\s*=\s*\{([\s\S]*?)\n\}/,
  );
  if (!block) throw new Error("COOKIE_REGISTRY not found in the backend module");
  const registry: Record<string, string> = {};
  for (const entry of block[1].matchAll(/"([^"]+)"\s*:\s*"([^"]+)"/g)) {
    registry[entry[1]] = entry[2];
  }
  return registry;
}

describe("web cookie disclosure rules", () => {
  test("covers the name Supabase actually derives, including chunks", () => {
    // Chunking appends .0/.1 for sessions too large for one cookie
    // (@supabase/ssr chunker), so both shapes have to be covered.
    const base = supabaseCookieName("https://lgdhvepyrzbnscqssgqq.supabase.co");
    expect(base).toBe("sb-lgdhvepyrzbnscqssgqq-auth-token");
    expect(disclosedCookieConcept(base)).toBe("sign_in");
    expect(disclosedCookieConcept(`${base}.0`)).toBe("sign_in");
    expect(disclosedCookieConcept(`${base}.1`)).toBe("sign_in");
  });

  test("covers Cloudflare bot and challenge cookies", () => {
    for (const name of ["__cf_bm", "cf_clearance", "cf_chl_rc_i"]) {
      expect(disclosedCookieConcept(name), name).toBe("security");
    }
  });

  test("refuses a cookie no rule covers", () => {
    expect(disclosedCookieConcept("argus-undisclosed")).toBeNull();
    expect(() => assertDisclosedCookie("argus-undisclosed")).toThrow(
      UndisclosedCookieError,
    );
  });

  test("covers every cookie the backend registry declares", () => {
    // The two registries describe one browser. A name the backend sets that no
    // web rule covers would pass the server adapter and fail observation.
    for (const name of Object.keys(backendCookieRegistry())) {
      expect(disclosedCookieConcept(name), name).not.toBeNull();
    }
  });

  test("every rule concept is a section item that exists in both locales", () => {
    for (const [locale, catalog] of Object.entries(CATALOGS)) {
      const items = catalog.legal.privacy.sections.cookies.items as Record<
        string,
        unknown
      >;
      for (const rule of COOKIE_DISCLOSURE_RULES) {
        expect(
          items,
          `${locale}: rule for ${rule.writer} maps to item "${rule.concept}", which the copy does not have`,
        ).toHaveProperty(rule.concept);
      }
    }
  });

  test("covers the name this deployment's Supabase project will actually use", () => {
    // The previous version of this test only checked a hardcoded example ref,
    // so a naming change or a configured cookieOptions.name would not have
    // been caught before production. Derive from the configured URL instead.
    const configured = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const urls = [
      configured,
      // Refs seen in the wild: plain, and the hyphenated form.
      "https://lgdhvepyrzbnscqssgqq.supabase.co",
      "https://abc-def-123.supabase.co",
    ].filter((url): url is string => Boolean(url));

    for (const url of urls) {
      const name = supabaseCookieName(url);
      expect(disclosedCookieConcept(name), `${url} -> ${name}`).toBe("sign_in");
      expect(disclosedCookieConcept(`${name}.0`), `${url} chunk`).toBe(
        "sign_in",
      );
      // The adapter path itself, not just the pattern, must accept it.
      expect(() => assertDisclosedCookie(name)).not.toThrow();
    }
  });

  test("accepts every name shape the auth libraries can derive", () => {
    // Enumerated from the packages rather than guessed: @supabase/ssr chunks
    // with `${key}.${i}`, and @supabase/auth-js derives
    // `${storageKey}-code-verifier` for PKCE. Missing the verifier made
    // assertDisclosedCookie throw inside the password-reset flow, which is a
    // broken feature and not only a disclosure gap.
    const base = supabaseCookieName("https://lgdhvepyrzbnscqssgqq.supabase.co");
    for (const name of [
      base,
      `${base}.0`,
      `${base}-code-verifier`,
      `${base}-code-verifier.0`,
    ]) {
      expect(disclosedCookieConcept(name), name).toBe("sign_in");
      expect(() => assertDisclosedCookie(name), name).not.toThrow();
    }
  });

  test("the password-reset path can write its cookies through the adapter", () => {
    // app/api/auth/recovery/route.ts calls createClient() from the gated
    // adapter, then resetPasswordForEmail, which writes the PKCE verifier.
    // Every name that flow produces has to pass the gate or recovery breaks in
    // development and CI, where the assertion throws.
    const route = readFileSync(
      join(import.meta.dir, "..", "app", "api", "auth", "recovery", "route.ts"),
      "utf-8",
    );
    expect(route).toContain("@/lib/supabase-server");

    const configured =
      process.env.NEXT_PUBLIC_SUPABASE_URL ??
      "https://lgdhvepyrzbnscqssgqq.supabase.co";
    const verifier = `${supabaseCookieName(configured)}-code-verifier`;
    expect(() => assertDisclosedCookie(verifier)).not.toThrow();
  });

  test("no code customizes the Supabase cookie name behind the registry's back", () => {
    // cookieOptions.name would replace the derived name entirely, so the
    // patterns above would stop describing reality. If this ever becomes
    // intentional, the chosen name has to join COOKIE_DISCLOSURE_RULES.
    for (const file of ["supabase-client.ts", "supabase-server.ts"]) {
      const source = readFileSync(
        join(import.meta.dir, "..", "lib", file),
        "utf-8",
      );
      expect(source, file).not.toContain("cookieOptions");
    }
  });

  test("the server adapter gates names before writing them", () => {
    const source = readFileSync(
      join(import.meta.dir, "..", "lib", "supabase-server.ts"),
      "utf-8",
    );
    expect(source).toContain("assertDisclosedCookie");
    // The gate must sit outside the Server Component try/catch, or a
    // disclosure failure would be swallowed with the rest.
    const gate = source.indexOf("assertDisclosedCookie(name)");
    const tryBlock = source.indexOf("try {", source.indexOf("setAll("));
    expect(gate).toBeGreaterThan(0);
    expect(gate).toBeLessThan(tryBlock);
  });
});
