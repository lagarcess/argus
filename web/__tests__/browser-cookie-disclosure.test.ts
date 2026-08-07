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
