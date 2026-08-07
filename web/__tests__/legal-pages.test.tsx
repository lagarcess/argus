import { describe, expect, test } from "bun:test";
import i18next from "i18next";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider } from "react-i18next";

import AlphaLegalPage from "../components/legal/AlphaLegalPage";
import en from "../public/locales/en/common.json";
import es419 from "../public/locales/es-419/common.json";

const SUPPORT_EMAIL = "support@get-argus.com";

const CATALOGS = { en, "es-419": es419 } as const;

const REPO_ROOT = join(import.meta.dir, "..", "..");
const BACKEND_ROOT = join(REPO_ROOT, "src");

// Every cookie the backend sets, mapped to the section item that discloses it.
// A new cookie with no entry here fails the coverage test by name.
const DISCLOSED_BACKEND_COOKIES: Record<string, string> = {
  "sb-auth-token": "sign_in",
  "sb-refresh-token": "sign_in",
  "argus-guest-handoff": "guest_handoff",
  "argus-guest-handoff-id": "guest_handoff",
};

type CookieWriter = { origin: string; argument: string; name: string | null };

// This scan is static and therefore best effort. It cannot follow a name
// through an arbitrary call graph, so it is built to fail loudly on anything
// it cannot resolve rather than to look complete. Treat an unresolvable hit as
// an undisclosed cookie, not as noise to filter out.
//
// Only set_cookie counts. A delete can only target a cookie some set_cookie
// already created, so it cannot introduce undisclosed browser state.
function backendCookieWriters(): CookieWriter[] {
  const found: CookieWriter[] = [];

  const files = readdirSync(BACKEND_ROOT, { recursive: true, encoding: "utf-8" })
    .filter((entry) => entry.endsWith(".py"));

  for (const relative of files) {
    const source = readFileSync(join(BACKEND_ROOT, relative), "utf-8");
    // Deliberately not `set_cookie\(`: `writer = response.set_cookie` binds the
    // method without ever calling it by name, and that file must still be read.
    if (!source.includes("set_cookie")) continue;

    // Module-level string constants, so a name passed by reference resolves.
    const constants = new Map<string, string>();
    for (const match of source.matchAll(/^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]*)"/gm)) {
      constants.set(match[1], match[2]);
    }

    const lineOf = (index: number) => source.slice(0, index).split("\n").length;

    // An alias hides every later call behind a name this scan cannot predict,
    // so the binding itself is the failure, not the calls downstream of it.
    for (const match of source.matchAll(
      /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*[A-Za-z_][A-Za-z0-9_.]*\.set_cookie\s*$/gm,
    )) {
      found.push({
        origin: `${relative}:${lineOf(match.index)}`,
        argument: `alias ${match[1]} = ...set_cookie`,
        name: null,
      });
    }

    for (const match of source.matchAll(/set_cookie\s*\(\s*([^,)\s]+)/g)) {
      const argument = match[1];
      const literal = argument.match(/^"([^"]*)"$/);
      found.push({
        origin: `${relative}:${lineOf(match.index)}`,
        argument,
        name: literal ? literal[1] : (constants.get(argument) ?? null),
      });
    }
  }

  return found;
}

// The phrase each concept must actually say in the shipped copy. Mapping a key
// to a bare label proves nothing on its own: the label has to be findable in
// what the reader sees, in every locale, or the map is decoration.
const STORAGE_CONCEPTS = {
  language: { en: "language", "es-419": "idioma" },
  appearance: { en: "appearance", "es-419": "apariencia" },
  layout: { en: "layout", "es-419": "diseño" },
  tips: { en: "tips you dismissed", "es-419": "avisos que descartaste" },
  temporary: {
    en: "conversations you marked temporary",
    "es-419": "conversaciones que marcaste como temporales",
  },
} as const;

type StorageConcept = keyof typeof STORAGE_CONCEPTS;

// Keys the scan can find in web/. Every one must still be discovered, so a
// refactor that hides a key fails rather than shrinking the inventory.
const DISCLOSED_STORAGE_KEYS: Record<string, StorageConcept> = {
  "argus-theme": "appearance",
  "argus:sidebar_mode": "layout",
  "argus:command_palette_layout": "layout",
  "argus:guest-hint:confirmation:v1": "tips",
  "argus:guest-hint:result:v1": "tips",
  "argus.memoryOptOutConversations.v1": "temporary",
};

// Keys a dependency writes under its own default, which never appear in our
// source at all. No scan can find these; they are disclosed by hand and listed
// here so the gap is visible instead of silent. Adding a storage-writing
// dependency means adding its key here.
const LIBRARY_DEFAULT_STORAGE_KEYS: Record<string, StorageConcept> = {
  // i18next-browser-languagedetector, caches: ["localStorage"] in lib/i18n.ts
  i18nextLng: "language",
};

type StorageWriter = { origin: string; argument: string; key: string | null };

// Symmetric to the cookie scan, and for the same reason: the first inventory
// counted explicit localStorage calls and missed the key a library sets.
function browserStorageWriters(): StorageWriter[] {
  const found: StorageWriter[] = [];

  const files = readdirSync(join(import.meta.dir, ".."), {
    recursive: true,
    encoding: "utf-8",
  }).filter(
    (entry) =>
      (entry.endsWith(".ts") || entry.endsWith(".tsx")) &&
      !entry.startsWith("node_modules") &&
      !entry.startsWith(".next") &&
      !entry.startsWith("__tests__") &&
      !entry.startsWith("e2e"),
  );

  for (const relative of files) {
    const source = readFileSync(join(import.meta.dir, "..", relative), "utf-8");
    const lineOf = (index: number) => source.slice(0, index).split("\n").length;

    const record = (index: number, argument: string) => {
      const origin = `${relative}:${lineOf(index)}`;
      const push = (key: string | null) => found.push({ origin, argument, key });

      const literal = argument.match(/^["'`]([^"'`]*)["'`]$/);
      if (literal) return push(literal[1]);

      // An indexed lookup reaches every value in the map, so every value has
      // to be disclosed, not just the branch this call site happens to take.
      const indexed = argument.match(/^([A-Za-z_$][\w$]*)\s*\[/);
      if (indexed) {
        const table = source.match(
          new RegExp(`\\b${indexed[1]}\\s*[:=][^={]*=?\\s*\\{([^}]*)\\}`),
        );
        const values = [...(table?.[1] ?? "").matchAll(/["'`]([^"'`]+)["'`]/g)];
        if (!values.length) return push(null);
        return values.forEach((value) => push(value[1]));
      }

      const constant = source.match(
        new RegExp(`\\b${argument}\\s*=\\s*["'\`]([^"'\`]*)["'\`]`),
      );
      push(constant?.[1] ?? null);
    };

    // Same evasion the cookie scan had: rebinding the handle hides every later
    // call behind a name this scan cannot predict, so the binding is the
    // failure. Covers `const s = window.localStorage` and `const { localStorage
    // } = window`.
    for (const match of source.matchAll(
      /(?:(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:(?:window|globalThis)\s*\.\s*)?(?:localStorage|sessionStorage)\b(?!\s*\.)|\{[^}]*\b(?:localStorage|sessionStorage)\b[^}]*\}\s*=\s*(?:window|globalThis))/g,
    )) {
      found.push({
        origin: `${relative}:${lineOf(match.index)}`,
        argument: `alias ${match[1] ?? "destructured"} = ...Storage`,
        key: null,
      });
    }

    for (const match of source.matchAll(
      /(?:localStorage|sessionStorage)\s*\.\s*(?:setItem|getItem|removeItem)\s*\(\s*([^,)]+?)\s*[,)]/g,
    )) {
      record(match.index, match[1].trim());
    }

    // Keys a dependency owns, declared where we configure it.
    for (const match of source.matchAll(/storageKey\s*=\s*["'{]+([^"'}]+)["'}]*/g)) {
      record(match.index, `"${match[1]}"`);
    }
  }

  return found;
}

async function renderLegal(
  locale: keyof typeof CATALOGS,
  kind: "terms" | "privacy",
): Promise<string> {
  const i18n = i18next.createInstance();
  await i18n.init({
    lng: locale,
    fallbackLng: false,
    interpolation: { escapeValue: false },
    resources: { [locale]: { translation: CATALOGS[locale] } },
  });

  const element: ReactElement = createElement(AlphaLegalPage, {
    kind,
    supportEmail: SUPPORT_EMAIL,
  });

  return renderToStaticMarkup(
    createElement(I18nextProvider, { i18n }, element),
  );
}

function legalStrings(catalog: (typeof CATALOGS)[keyof typeof CATALOGS]): string[] {
  const collected: string[] = [];
  const walk = (node: unknown): void => {
    if (typeof node === "string") {
      collected.push(node);
      return;
    }
    if (node && typeof node === "object") {
      Object.values(node as Record<string, unknown>).forEach(walk);
    }
  };
  walk(catalog.legal);
  return collected;
}

describe("legal page cookie and storage disclosure", () => {
  test("names every storage category Argus actually writes to the browser", async () => {
    const markup = await renderLegal("en", "privacy");

    expect(markup).toContain("Cookies and browser storage");
    expect(markup).toContain("Sign-in cookies");
    expect(markup).toContain("Guest handoff cookies");
    // path=/api/v1/auth reaches every auth route, not only sign-in.
    expect(markup).toContain("limited to Argus authentication routes");
    expect(markup).not.toContain("limited to the sign-in routes");
    expect(markup).toContain("Security cookies");
    expect(markup).toContain("Preferences you set");
    // The parties that actually set or hold browser state.
    expect(markup).toContain("Supabase authentication");
    expect(markup).toContain("Cloudflare Turnstile");
    expect(markup).toContain("local storage");
  });

  test("covers every cookie the backend sets, anywhere in src", () => {
    const writers = backendCookieWriters();
    const items = en.legal.privacy.sections.cookies.items as Record<
      string,
      unknown
    >;

    for (const writer of writers) {
      // A name the scan cannot resolve is not a pass. It is an unknown cookie,
      // so fail here rather than skipping it and reporting full coverage.
      expect(
        writer.name,
        `${writer.origin}: cookie name "${writer.argument}" could not be resolved to a literal, so its disclosure cannot be checked`,
      ).not.toBeNull();

      const item = DISCLOSED_BACKEND_COOKIES[writer.name as string];
      expect(
        item,
        `${writer.origin}: cookie "${writer.name}" is set but not mapped to a section item`,
      ).toBeDefined();
      expect(items, `section item "${item}" is missing`).toHaveProperty(item);
    }

    // Guard the scan itself: a refactor that stops matching would otherwise
    // pass by finding nothing at all.
    const names = new Set(writers.map((writer) => writer.name));
    for (const known of Object.keys(DISCLOSED_BACKEND_COOKIES)) {
      expect(names, `scan no longer finds the known cookie "${known}"`).toContain(
        known,
      );
    }
  });

  test("covers every browser storage key web/ writes", () => {
    const writers = browserStorageWriters();

    for (const writer of writers) {
      expect(
        writer.key,
        `${writer.origin}: storage key "${writer.argument}" could not be resolved to a literal, so its disclosure cannot be checked`,
      ).not.toBeNull();
      const key = writer.key as string;
      expect(
        DISCLOSED_STORAGE_KEYS[key] ?? LIBRARY_DEFAULT_STORAGE_KEYS[key],
        `${writer.origin}: storage key "${key}" is written but not covered by the preferences item`,
      ).toBeDefined();
    }

    const keys = new Set(writers.map((writer) => writer.key));
    for (const known of Object.keys(DISCLOSED_STORAGE_KEYS)) {
      expect(keys, `scan no longer finds the known key "${known}"`).toContain(
        known,
      );
    }
  });

  test("says every mapped concept out loud, in both locales", async () => {
    // Mapping a key to a concept is worthless unless the concept is findable
    // in what the reader actually sees. Drop a phrase from the copy and this
    // fails, which the key-to-concept map alone could never detect.
    const concepts = new Set<StorageConcept>([
      ...Object.values(DISCLOSED_STORAGE_KEYS),
      ...Object.values(LIBRARY_DEFAULT_STORAGE_KEYS),
    ]);
    expect(concepts.size).toBe(Object.keys(STORAGE_CONCEPTS).length);

    for (const locale of ["en", "es-419"] as const) {
      const preferences = CATALOGS[locale].legal.privacy.sections.cookies.items
        .preferences.body;
      const rendered = await renderLegal(locale, "privacy");
      for (const concept of concepts) {
        const phrase = STORAGE_CONCEPTS[concept][locale];
        expect(
          preferences,
          `${locale}: preferences copy never mentions "${concept}" ("${phrase}")`,
        ).toContain(phrase);
        expect(rendered, `${locale}: "${phrase}" is not rendered`).toContain(
          phrase,
        );
      }
    }
  });

  test("does not claim sign-in cookies expire with the browser session", async () => {
    // @supabase/ssr defaults to a 400-day maxAge, so a session-only claim is
    // false. This pins the correction rather than the wording around it.
    for (const locale of ["en", "es-419"] as const) {
      const signIn = CATALOGS[locale].legal.privacy.sections.cookies.items
        .sign_in.body;
      expect(signIn.toLowerCase(), locale).not.toContain("for your session");
      expect(signIn.toLowerCase(), locale).not.toContain("lo que dura tu sesión");
    }
    expect(await renderLegal("en", "privacy")).toContain(
      "They stay after you close the browser",
    );
  });

  test("states the no-tracking position that keeps the consent banner unnecessary", async () => {
    const markup = await renderLegal("en", "privacy");

    expect(markup).toContain("does not show a cookie consent banner");
    expect(markup).toContain("does not use advertising cookies");
    expect(markup).toContain("cross-site tracking");
    // Analytics are server-side, so they must not be described as browser state.
    expect(markup).toContain("run on Argus servers and store nothing in your browser");
  });

  test("ships the disclosure in both supported locales", async () => {
    const spanish = await renderLegal("es-419", "privacy");

    expect(spanish).toContain("Cookies y almacenamiento del navegador");
    expect(spanish).toContain("Cookies de inicio de sesión");
    expect(spanish).toContain("Cookies de traspaso de invitado");
    expect(spanish).toContain("rutas de autenticación de Argus");
    expect(spanish).toContain("Cookies de seguridad");
    expect(spanish).toContain("Preferencias que tú eliges");
    expect(spanish).toContain("no muestra un aviso de consentimiento de cookies");
  });

  test("keeps the cookie section keys parallel across locales", () => {
    for (const catalog of Object.values(CATALOGS)) {
      const cookies = catalog.legal.privacy.sections.cookies;
      expect(Object.keys(cookies).sort()).toEqual([
        "body",
        "body_after",
        "items",
        "title",
      ]);
      expect(Object.keys(cookies.items).sort()).toEqual([
        "guest_handoff",
        "preferences",
        "security",
        "sign_in",
      ]);
    }
  });
});

describe("legal page early-access wording", () => {
  test("drops private-alpha jargon from every user-facing legal string", () => {
    for (const [locale, catalog] of Object.entries(CATALOGS)) {
      for (const value of legalStrings(catalog)) {
        expect(value.toLowerCase(), `${locale}: ${value}`).not.toContain(
          "private alpha",
        );
        expect(value.toLowerCase(), `${locale}: ${value}`).not.toContain(
          "alfa privada",
        );
      }
    }
  });

  test("keeps the pre-release disclaimer that the wording change must not lose", async () => {
    const markup = await renderLegal("en", "terms");

    expect(markup).toContain("Early access availability and changes");
    expect(markup).toContain("provided as is, without warranties");
    expect(markup).toContain("may never reach a full release");
  });

  test("holds the founder-locked no-em-dash rule", () => {
    for (const [locale, catalog] of Object.entries(CATALOGS)) {
      for (const value of legalStrings(catalog)) {
        expect(value, `${locale}: ${value}`).not.toContain("—");
      }
    }
  });
});

describe("legal page navigation", () => {
  test("offers a back-to-Argus affordance at the top as well as the footer", async () => {
    for (const kind of ["terms", "privacy"] as const) {
      const markup = await renderLegal("en", kind);
      const header = markup.slice(0, markup.indexOf("<h1"));

      expect(header).toContain('aria-label="Back to Argus"');
      expect(header).toContain('href="/"');
      expect(markup.split('href="/"').length - 1).toBeGreaterThanOrEqual(2);
    }
  });

  test("cross-links the sibling legal page", async () => {
    expect(await renderLegal("en", "privacy")).toContain('href="/terms"');
    expect(await renderLegal("en", "terms")).toContain('href="/privacy"');
  });
});
