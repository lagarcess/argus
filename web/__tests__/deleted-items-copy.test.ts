import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");

function readLocale(locale: "en" | "es-419") {
  return JSON.parse(
    readFileSync(join(root, "public/locales", locale, "common.json"), "utf-8"),
  );
}

describe("Recently Deleted neutral restore copy", () => {
  test("English and Spanish state that deleted items are currently restorable", () => {
    const en = readLocale("en");
    const es = readLocale("es-419");

    expect(en.settings.data.deleted_retention_note).toBe(
      "Items in this list can currently be restored.",
    );
    expect(en.settings.data.deleted_item_note).toBe("Currently restorable.");
    expect(es.settings.data.deleted_retention_note).toBe(
      "Los elementos de esta lista se pueden restaurar actualmente.",
    );
    expect(es.settings.data.deleted_item_note).toBe("Se puede restaurar actualmente.");
  });

  test("Recently Deleted renders the neutral locale keys without retention promises", () => {
    const view = readFileSync(
      join(root, "components/settings/DeletedItemsView.tsx"),
      "utf-8",
    );

    expect(view).toContain('"settings.data.deleted_retention_note"');
    expect(view).toContain('"settings.data.deleted_item_note"');
    expect(view).not.toContain("Eligible for permanent deletion soon");
    expect(view).not.toContain("retention_expires_at");
  });
});
