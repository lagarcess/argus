import { describe, expect, test } from "bun:test";
import { privacyCopy } from "../components/privacy-copy";
import { businessContactEmail } from "../components/site-copy";
import { LOCALES } from "../lib/site-routes";

// The privacy text names the services that actually touch visitor data. When a
// service is added or replaced, this list and the text change together.
const PROCESSORS = ["Render", "Resend", "Apple", "Supabase", "Cloudflare"] as const;

const sectionText = (section: { paragraphs?: string[]; items?: string[] }) =>
  [...(section.paragraphs ?? []), ...(section.items ?? [])].join("\n");

describe.each(LOCALES)("privacy text (%s)", (locale) => {
  const copy = privacyCopy[locale];
  const byId = (id: string) => {
    const section = copy.sections.find((candidate) => candidate.id === id);
    if (!section) throw new Error(`missing section ${id}`);
    return section;
  };
  const providers = byId("providers").items ?? [];
  const allText = JSON.stringify(copy);

  test.each(PROCESSORS)("names %s once, in the providers section", (name) => {
    expect(providers.filter((item) => item.includes(name))).toHaveLength(1);
    const elsewhere = copy.sections
      .filter((section) => section.id !== "providers")
      .map(sectionText)
      .join("\n");
    expect(elsewhere).not.toContain(name);
  });

  test("mentions iCloud Mail once, beside the public address", () => {
    expect(allText.match(/iCloud/g)).toHaveLength(1);
    expect(providers.some((item) => item.includes("iCloud Mail") && item.includes(businessContactEmail))).toBe(true);
  });

  test("keeps the operator in its own short section", () => {
    const operator = byId("operator");
    expect(operator.paragraphs).toHaveLength(1);
    expect(sectionText(operator)).toContain(businessContactEmail);
    expect(allText).not.toMatch(/Cuadra LLC|Cuadrao LLC/);
  });

  test("does not claim data is received only in certain cases", () => {
    expect(allText).not.toMatch(/solo cuando|only when/i);
  });

  test("keeps the hosting IP-address disclosure", () => {
    expect(sectionText(byId("data"))).toMatch(/IP/);
  });

  test("does not describe the mailbox vaguely", () => {
    expect(allText).not.toContain("buzón de Cuadrao");
    expect(allText).not.toContain("Cuadrao's mailbox");
  });
});
