import { describe, expect, test } from "bun:test";

import en from "../public/locales/en/common.json";
import es419 from "../public/locales/es-419/common.json";

type LocaleTree = Record<string, unknown>;

const dossierCopy = {
  "command_palette.dossier_back": {
    en: "Dossier",
    es419: "Expediente",
  },
  "command_palette.decision_history": {
    en: "Decision history",
    es419: "Historial de decisiones",
  },
  "command_palette.decision_history_count": {
    en: "{{decided}} of {{total}} decided",
    es419: "{{decided}} de {{total}} con decisión",
  },
  "command_palette.no_decision_saved": {
    en: "No decision saved",
    es419: "Sin decisión guardada",
  },
  "command_palette.add_decision_short": {
    en: "Add decision",
    es419: "Agregar decisión",
  },
  "command_palette.change_decision_short": {
    en: "Change decision",
    es419: "Cambiar decisión",
  },
  "command_palette.open_in_conversation": {
    en: "Open in conversation",
    es419: "Abrir en la conversación",
  },
  "command_palette.load_older": {
    en: "Load older",
    es419: "Cargar anteriores",
  },
  "command_palette.decision_saved": {
    en: "Saved",
    es419: "Guardada",
  },
  "command_palette.decision_history_error": {
    en: "Could not load decision history",
    es419: "No se pudo cargar el historial de decisiones",
  },
  "command_palette.decision_history_retry": {
    en: "Try again",
    es419: "Intentar de nuevo",
  },
  "command_palette.decision_history_loading": {
    en: "Loading decision history",
    es419: "Cargando el historial de decisiones",
  },
  "command_palette.decision_history_loading_older": {
    en: "Loading older decisions",
    es419: "Cargando decisiones anteriores",
  },
  "command_palette.decision_note_label": {
    en: "Decision note: ",
    es419: "Nota de decisión: ",
  },
  "command_palette.decision_note_editor_label": {
    en: "Decision note",
    es419: "Nota de decisión",
  },
  "command_palette.run_fresh_short": {
    en: "Run it fresh",
    es419: "Volver a probar",
  },
} as const;

function translationAt(locale: LocaleTree, dottedKey: string): string | undefined {
  let value: unknown = locale;
  for (const segment of dottedKey.split(".")) {
    if (typeof value !== "object" || value === null || !(segment in value)) {
      return undefined;
    }
    value = (value as LocaleTree)[segment];
  }
  return typeof value === "string" ? value : undefined;
}

function interpolationVariables(value: string): string[] {
  return [...value.matchAll(/{{\s*([a-zA-Z0-9_]+)\s*}}/g)]
    .map((match) => match[1])
    .sort();
}

describe("Omnisearch dossier-history locales", () => {
  test("provides the locked English and natural es-419 copy", () => {
    for (const [key, expected] of Object.entries(dossierCopy)) {
      expect(translationAt(en, key), `${key} English copy`).toBe(expected.en);
      expect(translationAt(es419, key), `${key} es-419 copy`).toBe(
        expected.es419,
      );
    }
  });

  test("keeps interpolation variables equivalent across supported locales", () => {
    for (const key of Object.keys(dossierCopy)) {
      const english = translationAt(en, key);
      const spanish = translationAt(es419, key);

      expect(english, `${key} English copy`).toBeDefined();
      expect(spanish, `${key} es-419 copy`).toBeDefined();
      expect(interpolationVariables(spanish ?? ""), key).toEqual(
        interpolationVariables(english ?? ""),
      );
    }
  });
});
