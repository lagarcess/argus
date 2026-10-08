import { describe, expect, test } from "bun:test";
import { privacyCopy } from "../components/privacy-copy";
import { businessContactEmail } from "../components/site-copy";
import { LOCALES } from "../lib/site-routes";

// The privacy text names the services that actually touch visitor data. When a
// service is added or replaced, this list and the text change together.
const PROCESSORS = ["Render", "Resend", "Apple", "Supabase", "Cloudflare"] as const;

describe.each(LOCALES)("privacy text (%s)", (locale) => {
  const copy = privacyCopy[locale];
  const processors = copy.sections.find((section) => section.items)?.items ?? [];

  test.each(PROCESSORS)("names %s as a processor", (name) => {
    expect(processors.some((item) => item.includes(name))).toBe(true);
  });

  test("names iCloud Mail and the public address for the mailbox", () => {
    const text = JSON.stringify(copy.sections);
    expect(text).toContain("iCloud Mail");
    expect(text).toContain(businessContactEmail);
  });

  test("no longer describes the mailbox only as Cuadrao's mailbox", () => {
    const text = JSON.stringify(copy.sections);
    expect(text).not.toContain("buzón de Cuadrao");
    expect(text).not.toContain("Cuadrao's mailbox");
  });
});
