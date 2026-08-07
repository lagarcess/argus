import { describe, expect, test } from "bun:test";
import i18next from "i18next";
import { createElement, type ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider } from "react-i18next";

import AlphaLegalPage from "../components/legal/AlphaLegalPage";
import en from "../public/locales/en/common.json";
import es419 from "../public/locales/es-419/common.json";

const SUPPORT_EMAIL = "support@get-argus.com";

const CATALOGS = { en, "es-419": es419 } as const;

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
    expect(markup).toContain("Security cookies");
    expect(markup).toContain("Preferences you set");
    // The three parties that actually set or hold browser state.
    expect(markup).toContain("Supabase authentication");
    expect(markup).toContain("Cloudflare Turnstile");
    expect(markup).toContain("local storage");
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
